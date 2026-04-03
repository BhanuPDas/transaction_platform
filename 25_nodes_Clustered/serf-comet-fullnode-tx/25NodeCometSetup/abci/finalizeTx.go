package main

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"github.com/cometbft/cometbft/abci/types"
	"strconv"
	"time"
)

func (app *MyApp) FinalizeBlock(_ context.Context, req *types.FinalizeBlockRequest) (*types.FinalizeBlockResponse, error) {
	app.Logger.Info(fmt.Sprintf("=== [FINALIZE BLOCK START] (Block: %d) ===", req.Height))
	var meta struct {
		Type string `json:"type"`
	}
	app.punishValidators(req)
	var txStrings []string
	for _, txBytes := range req.Txs {
		txStrings = append(txStrings, fmt.Sprintf("%x", txBytes))
	}
	app.Logger.Info(fmt.Sprintf("ABCI: Processing transactions for block. Tx count: %d, Txs: %v", len(req.Txs), txStrings))
	app.State.Height = req.Height
	txResults := make([]*types.ExecTxResult, 0, len(req.Txs))
	for _, txBytes := range req.Txs {
		decodedStrTx, err2 := base64.StdEncoding.DecodeString(string(txBytes))
		if err2 != nil {
			app.Logger.Error(fmt.Sprintf("ABCI ERROR: Failed to base64 decode tx: %v, Payload: %s", err2, string(txBytes)))
			txResults = append(txResults, &types.ExecTxResult{
				Code: 1,
				Log:  "Failed to base64 decode tx",
			})
			continue
		}
		if err := json.Unmarshal(decodedStrTx, &meta); err != nil {
			txResults = append(txResults, &types.ExecTxResult{Code: 2, Log: "Bad JSON"})
			continue
		}
		if meta.Type == TransferType {
			result := app.ExecuteTx(decodedStrTx, req)
			txResults = append(txResults, result)
		} else if meta.Type == AddValidatorType || meta.Type == RemoveValidatorType || meta.Type == UpdateValidatorType {
			var vtx Validators
			if err := json.Unmarshal(decodedStrTx, &vtx); err != nil {
				txResults = append(txResults, &types.ExecTxResult{Code: 2, Log: "Bad JSON"})
				continue
			}
			app.UpdateValidator(string(decodedStrTx))
			txResults = append(txResults, &types.ExecTxResult{Code: CodeTypeOK, Log: "Validator Request Executed"})
		} else {
			txResults = append(txResults, &types.ExecTxResult{Code: 7, Log: "Unknown tx type"})
		}
	}
	app.ProcessExpiredTxs(req)
	app.LastBlockHeight = req.Height
	app.Logger.Info(fmt.Sprintf("=== [FINALIZE BLOCK END] (Block: %d) ===", app.LastBlockHeight))
	return &types.FinalizeBlockResponse{TxResults: txResults, AppHash: app.State.Hash(), ValidatorUpdates: app.ValUpdates}, nil
}

func (app *MyApp) ExecuteTx(decodedStrTx []byte, req *types.FinalizeBlockRequest) *types.ExecTxResult {
	var tx TransferTransaction
	if err := json.Unmarshal(decodedStrTx, &tx); err != nil {
		return &types.ExecTxResult{Code: 2, Log: "Bad JSON"}
	}
	txHash := GenerateTxHash(decodedStrTx)
	txKey := "tx:" + txHash
	_, closer, err := app.State.DB.Get([]byte(txKey))
	if err == nil {
		_ = closer.Close()
		app.Logger.Info("Duplicate transaction detected, skipping", "txHash", txHash)
		return &types.ExecTxResult{Code: CodeTypeOK, Log: "Duplicate tx skipped"}
	}
	startTime, endTime, err := ComputeEndTime(tx)
	if err != nil {
		app.Logger.Error(fmt.Sprintf("ABCI ERROR: Failed to compute end time: %v", err))
		app.Logger.Error(fmt.Sprintf("Invalid time format: %v", err))
		return &types.ExecTxResult{Code: 3, Log: fmt.Sprintf("Invalid tx_start_ts: %v", err)}
	}
	app.Logger.Info(fmt.Sprintf("Transaction %s started at %s and will finish at %s", txHash, startTime, endTime))
	if tx.Seller.Name == "" {
		txDetails := TxDetails{
			Status:    StatusFailed,
			TxHash:    txHash,
			Tx:        tx,
			TxEndUnix: endTime.Unix(),
			TxEndTs:   (req.Time.UTC()).Format(time.RFC3339Nano),
			Log:       "No Seller Found For The Buyer Demand",
		}
		app.SaveTx(txHash, txDetails, endTime)
		return &types.ExecTxResult{Code: CodeTypeOK, Log: "Executed"}
	}
	hasBudget, _ := HasHighBudget(tx.Buyer, tx.Seller)
	if !hasBudget {
		txDetails := TxDetails{
			Status:    StatusFailed,
			TxHash:    txHash,
			Tx:        tx,
			TxEndUnix: endTime.Unix(),
			TxEndTs:   (req.Time.UTC()).Format(time.RFC3339Nano),
			Log:       "Buyer Has Very Low Budget For The Resources",
		}
		app.SaveTx(txHash, txDetails, endTime)
		return &types.ExecTxResult{Code: CodeTypeOK, Log: "Executed"}
	}
	if endTime.Before(req.Time.UTC()) {
		txDetails := TxDetails{
			Status:    StatusExpired,
			TxHash:    txHash,
			Tx:        tx,
			TxEndUnix: endTime.Unix(),
			TxEndTs:   (req.Time.UTC()).Format(time.RFC3339Nano),
			Log:       "Invalid lease duration, transaction expired before it is processed",
		}
		app.SaveTx(txHash, txDetails, endTime)
		return &types.ExecTxResult{Code: CodeTypeOK, Log: "Executed"}
	}

	fromBalance, fromExists := app.State.Ledger[tx.Buyer.Name]
	_, toExists := app.State.Ledger[tx.Seller.Name]
	var events []types.Event
	if fromExists && toExists {
		if fromBalance < tx.Amount {
			return &types.ExecTxResult{Code: 5, Log: "Insufficient funds"}
		}
		app.State.Ledger[tx.Buyer.Name] -= tx.Amount
		app.State.Ledger[tx.Seller.Name] += tx.Amount
	}
	if fromExists && !toExists {
		if fromBalance < tx.Amount {
			return &types.ExecTxResult{Code: 5, Log: "Insufficient funds"}
		}
		app.State.Ledger[tx.Buyer.Name] -= tx.Amount
		events = []types.Event{
			{
				Type: "relay_transfer",
				Attributes: []types.EventAttribute{
					{Key: "from", Value: tx.Buyer.Name, Index: true},
					{Key: "to", Value: tx.Seller.Name, Index: true},
					{Key: "amount", Value: strconv.FormatInt(tx.Amount, 10), Index: true},
					{Key: "timestamp", Value: tx.TxStartTs, Index: false},
				},
			},
		}

		app.Logger.Info("Relay processing", "from", tx.Buyer.Name, "to", tx.Seller.Name, "fromExists", fromExists, "toExists", toExists)
	}
	if !fromExists && toExists {
		app.State.Ledger[tx.Seller.Name] += tx.Amount
	}
	if !fromExists && !toExists {
		return &types.ExecTxResult{Code: 4, Log: "transaction not relevant to this cluster"}
	}
	txDetails := TxDetails{
		Status:    StatusOnGoing,
		TxHash:    txHash,
		Tx:        tx,
		TxEndUnix: endTime.Unix(),
		Log:       "Processing Transaction",
	}
	app.SaveTx(txHash, txDetails, endTime)
	app.State.Size++
	return &types.ExecTxResult{Code: CodeTypeOK, Log: "Executed", Events: events}
}

func ComputeEndTime(tx TransferTransaction) (time.Time, time.Time, error) {
	if tx.TxStartTs == "" {
		return time.Time{}, time.Time{}, fmt.Errorf("tx_start_ts is empty")
	}
	startTime, err := time.Parse(time.RFC3339Nano, tx.TxStartTs)
	if err != nil {
		return time.Time{}, time.Time{}, err
	}
	endTime := startTime.Add(time.Duration(tx.LeaseDuration) * time.Second)
	return startTime, endTime, nil
}

func HasHighBudget(buyer BuyerInfo, seller SellerInfo) (bool, error) {
	totalBudget := 0.0
	totalPrice := 0.0
	for resource, demand := range buyer.Resources {
		if demand.DemandPerUnit == 0 {
			continue
		}
		sellerPrice, ok := seller.Price[resource]
		if !ok {
			return false, fmt.Errorf("seller %s does not have pricing for resource: %s", seller.IP, resource)
		}
		totalBudget += demand.Budget
		totalPrice += sellerPrice
	}
	if totalBudget == 0 {
		return false, fmt.Errorf("no valid resource demand found for buyer %s", buyer.Name)
	}
	return totalBudget >= totalPrice, nil
}
