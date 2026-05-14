package main

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"github.com/cometbft/cometbft/abci/types"
	"strings"
)

func (app *MyApp) CheckTx(_ context.Context, req *types.CheckTxRequest) (*types.CheckTxResponse, error) {
	app.Logger.Info(fmt.Sprintf("--- CHECK TX START---"))
	app.Logger.Info(fmt.Sprintf("Received raw transaction: %s", string(req.Tx)))
	var meta struct {
		Type string `json:"type"`
	}
	rawTx := string(req.Tx)
	if strings.HasPrefix(rawTx, "\"") && strings.HasSuffix(rawTx, "\"") {
		rawTx = rawTx[1 : len(rawTx)-1]
	}
	decodedTx, err := base64.StdEncoding.DecodeString(rawTx)
	if err != nil {
		app.Logger.Error(fmt.Sprintf("ABCI CheckTx ERROR: Base64 decode failed: %v", err))
		return &types.CheckTxResponse{Code: 1, Log: fmt.Sprintf("Base64 decode failed: %v", err)}, nil
	}
	app.Logger.Info(fmt.Sprintf("ABCI CheckTx: Successfully Base64 decoded to JSON: %s", string(decodedTx)))
	if err := json.Unmarshal(decodedTx, &meta); err != nil {
		msg := fmt.Sprintf("ERROR: Failed to parse JSON: %v", err)
		return &types.CheckTxResponse{Code: 2, Log: msg}, nil
	}
	switch meta.Type {
	case TransferType:
		txRes, err := app.CheckTransferTX(string(decodedTx))
		if err != nil {
			app.Logger.Error(fmt.Sprintf("ERROR: Failed to validate transaction: %v", err))
		}
		return txRes, nil
	case AddValidatorType, RemoveValidatorType, UpdateValidatorType:
		vtxRes, err := app.CheckValidatorTX(string(decodedTx))
		if err != nil {
			app.Logger.Error(fmt.Sprintf("ERROR: Failed to check validator transaction: %v", err))
		}
		return vtxRes, nil
	}
	return &types.CheckTxResponse{Code: CodeTypeInvalidTxFormat, Log: "Invalid Transaction Type"}, nil
}

func (app *MyApp) CheckTransferTX(reqtx string) (*types.CheckTxResponse, error) {
	var tx TransferTransaction
	if err := json.Unmarshal([]byte(reqtx), &tx); err != nil {
		msg := fmt.Sprintf("ERROR: Failed to parse JSON: %v", err)
		return &types.CheckTxResponse{Code: 2, Log: msg}, nil
	}
	if tx.Type == "" || tx.Buyer.Name == "" || tx.TxStartTs == "" {
		logMsg := "ABCI CheckTx ERROR: Missing one or more required fields (type, from_node, timestamp)."
		app.Logger.Error(logMsg)
		return &types.CheckTxResponse{Code: 3, Log: logMsg}, nil
	}
	fromBalance, fromExists := app.State.Ledger[tx.Buyer.Name]
	_, toExists := app.State.Ledger[tx.Seller.Name]
	if !fromExists && !toExists {
		return &types.CheckTxResponse{
			Code: 4,
			Log:  "transaction does not belong to this cluster",
		}, nil
	}
	if fromExists {
		if fromBalance < tx.Amount {
			msg := fmt.Sprintf("ERROR: Insufficient funds for '%s'. Has %d, needs %d",
				tx.Buyer.Name, fromBalance, tx.Amount)
			return &types.CheckTxResponse{Code: 5, Log: msg}, nil
		}
	}
	app.Logger.Info(fmt.Sprintf("Transaction OK. From=%s, To=%s, Amount=%d", tx.Buyer.Name, tx.Seller.Name, tx.Amount))
	return &types.CheckTxResponse{Code: CodeTypeOK, Log: "Transaction format and logic OK."}, nil
}
