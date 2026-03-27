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
	app.logger.Info(fmt.Sprintf("=== [FINALIZE BLOCK START] (Block: %d) ===", req.Height))
	var meta struct {
		Type string `json:"type"`
	}
	app.punishValidators(req)
	var txStrings []string
	for _, txBytes := range req.Txs {
		txStrings = append(txStrings, fmt.Sprintf("%x", txBytes))
	}
	app.logger.Info(fmt.Sprintf("ABCI: Processing transactions for block. Tx count: %d, Txs: %v", len(req.Txs), txStrings))
	app.state.Height = req.Height
	txResults := make([]*types.ExecTxResult, 0, len(req.Txs))
	for _, txBytes := range req.Txs {
		decodedStrTx, err2 := base64.StdEncoding.DecodeString(string(txBytes))
		if err2 != nil {
			app.logger.Error(fmt.Sprintf("ABCI ERROR: Failed to base64 decode tx: %v, Payload: %s", err2, string(txBytes)))
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
			app.ExecuteTx(req, decodedStrTx, txResults)
		} else if meta.Type == AddValidatorType || meta.Type == RemoveValidatorType || meta.Type == UpdateValidatorType {
			var vtx Validators
			if err := json.Unmarshal(decodedStrTx, &vtx); err != nil {
				txResults = append(txResults, &types.ExecTxResult{Code: 2, Log: "Bad JSON"})
				continue
			}
			app.UpdateValidator(string(decodedStrTx))
			txResults = append(txResults, &types.ExecTxResult{Code: CodeTypeOK, Log: "Validator Request Executed"})
		}
	}
	app.ProcessExpiredTxs(req)
	app.lastBlockHeight = req.Height
	app.logger.Info(fmt.Sprintf("=== [FINALIZE BLOCK END] (Block: %d) ===", app.lastBlockHeight))
	return &types.FinalizeBlockResponse{TxResults: txResults, AppHash: app.state.Hash(), ValidatorUpdates: app.valUpdates}, nil
}

func (app *MyApp) ExecuteTx(req *types.FinalizeBlockRequest, decodedStrTx []byte, txResults []*types.ExecTxResult) {
	now := req.Time.UTC()
	var tx TransferTransaction
	if err := json.Unmarshal(decodedStrTx, &tx); err != nil {
		txResults = append(txResults, &types.ExecTxResult{Code: 2, Log: "Bad JSON"})
		return
	}
	txHash := GenerateTxHash(decodedStrTx)
	txKey := "tx:" + txHash
	_, closer, err := app.state.DB.Get([]byte(txKey))
	if err == nil {
		_ = closer.Close()
		app.logger.Info("Duplicate transaction detected, skipping", "txHash", txHash)

		txResults = append(txResults, &types.ExecTxResult{
			Code: CodeTypeOK,
			Log:  "Duplicate tx skipped",
		})
		return
	}
	startTime, endTime, err := ComputeEndTime(tx)
	if err != nil {
		app.logger.Error(fmt.Sprintf("ABCI ERROR: Failed to compute end time: %v", err))
		app.logger.Error(fmt.Sprintf("Invalid time format: %v", err))
		return
	}
	app.logger.Info(fmt.Sprintf("Transaction %s started at %s and will finish at %s", txHash, startTime, endTime))

	fromBalance, fromExists := app.state.Ledger[tx.Buyer]
	_, toExists := app.state.Ledger[tx.Seller]
	var events []types.Event
	if fromExists && toExists {
		if fromBalance < tx.Amount {
			txResults = append(txResults, &types.ExecTxResult{
				Code: 7,
				Log:  "Insufficient funds",
			})
			return
		}
		app.state.Ledger[tx.Buyer] -= tx.Amount
		app.state.Ledger[tx.Seller] += tx.Amount
	}
	if fromExists && !toExists {
		if fromBalance < tx.Amount {
			txResults = append(txResults, &types.ExecTxResult{
				Code: 7,
				Log:  "Insufficient funds",
			})
			return
		}
		app.state.Ledger[tx.Buyer] -= tx.Amount
		events = []types.Event{
			{
				Type: "relay_transfer",
				Attributes: []types.EventAttribute{
					{Key: "from", Value: tx.Buyer, Index: true},
					{Key: "to", Value: tx.Seller, Index: true},
					{Key: "amount", Value: strconv.FormatInt(tx.Amount, 10), Index: true},
					{Key: "timestamp", Value: tx.TxStartTs, Index: false},
				},
			},
		}

		app.logger.Info("Relay processing", "from", tx.Buyer, "to", tx.Seller, "fromExists", fromExists, "toExists", toExists)
	}
	if !fromExists && toExists {
		app.state.Ledger[tx.Seller] += tx.Amount
	}
	if !fromExists && !toExists {
		txResults = append(txResults, &types.ExecTxResult{
			Code: 8,
			Log:  "transaction not relevant to this cluster",
		})
		return
	}
	status := StatusOnGoing
	if now.After(endTime) {
		status = StatusCompleted
	}
	txDetails := TxDetails{
		Status: status,
		TxHash: txHash,
		TxObj:  tx,
		Log:    "Processing Transaction",
	}
	if status == StatusCompleted {
		txDetails.TxEndTs = now.Format(time.RFC3339Nano)
		txDetails.Log = "Transaction Completed"
	}
	app.SaveTx(txHash, txDetails, endTime)
	txResults = append(txResults, &types.ExecTxResult{
		Code:   CodeTypeOK,
		Log:    "Executed",
		Events: events,
	})
	app.state.Size++
}

func ComputeEndTime(tx TransferTransaction) (time.Time, time.Time, error) {
	startTime, err := time.Parse(time.RFC3339Nano, tx.TxStartTs)
	if err != nil {
		return time.Time{}, time.Time{}, err
	}
	endTime := startTime.Add(time.Duration(tx.LeaseDuration) * time.Second)
	return startTime, endTime, nil
}
