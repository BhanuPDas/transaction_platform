package main

import (
	"context"
	"fmt"
	"github.com/cometbft/cometbft/abci/types"
)

func (app *MyApp) Commit(_ context.Context, _ *types.CommitRequest) (*types.CommitResponse, error) {
	app.Logger.Info(fmt.Sprintf("[Committing Transaction] (Block: %d) +++", app.LastBlockHeight))
	app.Logger.Info(fmt.Sprintf("Persisting Transaction to DB"))
	app.SaveToDB()
	resp := &types.CommitResponse{}
	if app.RetainBlocks > 0 && app.State.Height >= app.RetainBlocks {
		resp.RetainHeight = app.State.Height - app.RetainBlocks + 1
	}
	return resp, nil
}
