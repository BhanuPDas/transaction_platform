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
	app.logger.Info(fmt.Sprintf("--- CHECK TX START---"))
	app.logger.Info(fmt.Sprintf("Received raw transaction: %s", string(req.Tx)))
	var meta struct {
		Type string `json:"type"`
	}
	rawTx := string(req.Tx)
	if strings.HasPrefix(rawTx, "\"") && strings.HasSuffix(rawTx, "\"") {
		rawTx = rawTx[1 : len(rawTx)-1]
	}
	decodedTx, err := base64.StdEncoding.DecodeString(rawTx)
	if err != nil {
		app.logger.Error(fmt.Sprintf("ABCI CheckTx ERROR: Base64 decode failed: %v", err))
		return &types.CheckTxResponse{Code: 1, Log: fmt.Sprintf("Base64 decode failed: %v", err)}, nil
	}
	app.logger.Info(fmt.Sprintf("ABCI CheckTx: Successfully Base64 decoded to JSON: %s", string(decodedTx)))
	if err := json.Unmarshal(decodedTx, &meta); err != nil {
		msg := fmt.Sprintf("ERROR: Failed to parse JSON: %v", err)
		return &types.CheckTxResponse{Code: 2, Log: msg}, nil
	}
	switch meta.Type {
	case TransferType:
		txRes, err := app.CheckTransferTX(string(decodedTx))
		if err != nil {
			app.logger.Error(fmt.Sprintf("ERROR: Failed to validate transaction: %v", err))
		}
		return txRes, nil
	case AddValidatorType, RemoveValidatorType, UpdateValidatorType:
		vtxRes, err := app.CheckValidatorTX(string(decodedTx))
		if err != nil {
			app.logger.Error(fmt.Sprintf("ERROR: Failed to check validator transaction: %v", err))
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
	if tx.Type == "" || tx.Buyer == "" || tx.Seller == "" || tx.Amount <= 0 || tx.TxStartTs == "" {
		logMsg := "ABCI CheckTx ERROR: Missing one or more required fields (type, from_node, to_node, amount, timestamp)."
		app.logger.Error(logMsg)
		return &types.CheckTxResponse{Code: 4, Log: logMsg}, nil
	}
	fromBalance, fromExists := app.state.Ledger[tx.Buyer]
	_, toExists := app.state.Ledger[tx.Seller]
	if !fromExists && !toExists {
		return &types.CheckTxResponse{
			Code: 6,
			Log:  "transaction does not belong to this cluster",
		}, nil
	}
	if fromExists {
		if fromBalance < tx.Amount {
			msg := fmt.Sprintf("ERROR: Insufficient funds for '%s'. Has %d, needs %d",
				tx.Buyer, fromBalance, tx.Amount)
			return &types.CheckTxResponse{Code: 7, Log: msg}, nil
		}
	}
	app.logger.Info(fmt.Sprintf("Transaction OK. From=%s, To=%s, Amount=%d", tx.Buyer, tx.Seller, tx.Amount))
	return &types.CheckTxResponse{Code: CodeTypeOK, Log: "Transaction format and logic OK."}, nil
}
