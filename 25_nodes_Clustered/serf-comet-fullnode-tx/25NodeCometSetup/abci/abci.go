package main

import (
	"context"
	"fmt"

	"github.com/cockroachdb/pebble/v2"
	"github.com/cometbft/cometbft/abci/types"
	"github.com/cometbft/cometbft/crypto"
	cryptoenc "github.com/cometbft/cometbft/crypto/encoding"
	"github.com/cometbft/cometbft/libs/log"
	"github.com/cometbft/cometbft/version"
)

func NewMyApp(db *pebble.DB, logger log.Logger, cluster *AppConfig) *MyApp {
	app := &MyApp{
		State: &State{
			DB:        db,
			Ledger:    make(map[string]int64),
			Validator: make([]types.ValidatorUpdate, 0),
		},
		ValAddrToPubKeyMap:         make(map[string]crypto.PubKey),
		Logger:                     logger,
		UpdatedValidatorsThisBlock: make(map[string]struct{}),
		Cls:                        cluster.ClusterName,
	}
	app.Logger.Info(fmt.Sprintf("Loading Data from DB..."))
	app.LoadFromDB()
	return app
}

func (app *MyApp) Info(_ context.Context, req *types.InfoRequest) (*types.InfoResponse, error) {
	app.Logger.Info(fmt.Sprintf("CometBFT Node connected. Version: %s, ABCIVersion: %s", req.Version, req.AbciVersion))
	return &types.InfoResponse{
		Version:          version.ABCIVersion,
		AppVersion:       AppVersion,
		LastBlockHeight:  app.State.Height,
		LastBlockAppHash: app.State.Hash(),
	}, nil
}

func (app *MyApp) InitChain(_ context.Context, req *types.InitChainRequest) (*types.InitChainResponse, error) {
	app.Logger.Info(fmt.Sprintf("COMETBFT Initialization Start - INIT CHAIN"))
	if len(app.State.Ledger) == 0 {
		app.Logger.Info(fmt.Sprintf("No existing balances found, initializing defaults for all nodes..."))
		if len(app.Cls) > 0 && app.Cls[0] == "clusterA" {
			for i := 1; i <= 12; i++ {
				key := fmt.Sprintf("serf%d", i)
				app.State.Ledger[key] = 1000000
			}
		} else if len(app.Cls) > 0 && app.Cls[0] == "clusterB" {
			for i := 13; i <= 25; i++ {
				key := fmt.Sprintf("serf%d", i)
				app.State.Ledger[key] = 1000000
			}
		}
	} else {
		app.Logger.Info(fmt.Sprintf("Successfully restored balances from Pebble DB."))
	}
	app.Logger.Info(fmt.Sprintf("Ledger initialized with %d accounts.", len(app.State.Ledger)))
	if len(app.State.Validator) == 0 {
		app.Logger.Error(fmt.Sprintf("No validators found in DB...Add validators for consensus"))
		for _, v := range req.Validators {
			pubkey, _ := cryptoenc.PubKeyFromTypeAndBytes(v.PubKeyType, v.PubKeyBytes)
			addr := string(pubkey.Address())
			app.State.Validator = append(app.State.Validator, v)
			app.ValAddrToPubKeyMap[addr] = pubkey
			app.ValUpdates = append(app.ValUpdates, v)
		}
	}
	app.Logger.Info(fmt.Sprintf("Total validators initialized: %d", len(app.State.Validator)))
	app.LastBlockHeight = req.InitialHeight
	app.Logger.Info(fmt.Sprintf("COMETBFT Initialization End - INIT CHAIN"))
	return &types.InitChainResponse{Validators: app.ValUpdates, AppHash: app.State.Hash()}, nil
}
