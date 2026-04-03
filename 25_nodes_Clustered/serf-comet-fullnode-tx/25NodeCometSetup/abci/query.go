package main

import (
	"context"
	"encoding/json"
	"fmt"
	"github.com/cometbft/cometbft/abci/types"
)

func (app *MyApp) Query(_ context.Context, query *types.QueryRequest) (*types.QueryResponse, error) {
	app.Logger.Info("Executing Application Query.")
	resp := types.QueryResponse{Key: query.Data}
	switch string(query.Data) {
	case "balance":
		resultBytes, err := json.Marshal(app.State.Ledger)
		if err != nil {
			return nil, err
		}
		resp.Log = "Full ledger State"
		resp.Value = resultBytes
		return &resp, nil
	case "tx":
		txs := app.FetchTxs()
		resultBytes, err := json.Marshal(txs)
		if err != nil {
			return nil, err
		}
		resp.Log = fmt.Sprintf("Total transactions found: %d", len(txs))
		resp.Value = resultBytes
		return &resp, nil
	default:
		resp.Log = "unknown query"
		resp.Value = []byte{}
		return &resp, nil
	}
}
