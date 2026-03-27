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
		state: &State{
			DB:        db,
			Ledger:    make(map[string]int64),
			Validator: make([]types.ValidatorUpdate, 0),
		},
		valAddrToPubKeyMap:         make(map[string]crypto.PubKey),
		logger:                     logger,
		updatedValidatorsThisBlock: make(map[string]struct{}),
		cls:                        cluster.ClusterName,
	}
	app.logger.Info(fmt.Sprintf("Loading Data from DB..."))
	app.LoadFromDB()
	return app
}

func (app *MyApp) Info(_ context.Context, req *types.InfoRequest) (*types.InfoResponse, error) {
	app.logger.Info(fmt.Sprintf("CometBFT Node connected. Version: %s, ABCIVersion: %s", req.Version, req.AbciVersion))
	return &types.InfoResponse{
		Version:          version.ABCIVersion,
		AppVersion:       AppVersion,
		LastBlockHeight:  app.state.Height,
		LastBlockAppHash: app.state.Hash(),
	}, nil
}

func (app *MyApp) InitChain(_ context.Context, req *types.InitChainRequest) (*types.InitChainResponse, error) {
	app.logger.Info(fmt.Sprintf("COMETBFT Initialization Start - INIT CHAIN"))
	if len(app.state.Ledger) == 0 {
		app.logger.Info(fmt.Sprintf("No existing balances found, initializing defaults for all nodes..."))
		if len(app.cls) > 0 && app.cls[0] == "clusterA" {
			for i := 1; i <= 12; i++ {
				key := fmt.Sprintf("serf%d", i)
				app.state.Ledger[key] = 10000
			}
		} else if len(app.cls) > 0 && app.cls[0] == "clusterB" {
			for i := 13; i <= 25; i++ {
				key := fmt.Sprintf("serf%d", i)
				app.state.Ledger[key] = 10000
			}
		}
	} else {
		app.logger.Info(fmt.Sprintf("Successfully restored balances from Pebble DB."))
	}
	app.logger.Info(fmt.Sprintf("Ledger initialized with %d accounts.", len(app.state.Ledger)))
	if len(app.state.Validator) == 0 {
		app.logger.Error(fmt.Sprintf("No validators found in DB...Add validators for consensus"))
		for _, v := range req.Validators {
			pubkey, _ := cryptoenc.PubKeyFromTypeAndBytes(v.PubKeyType, v.PubKeyBytes)
			addr := string(pubkey.Address())
			app.state.Validator = append(app.state.Validator, v)
			app.valAddrToPubKeyMap[addr] = pubkey
			app.valUpdates = append(app.valUpdates, v)
		}
	}
	app.logger.Info(fmt.Sprintf("Total validators initialized: %d", len(app.state.Validator)))
	app.lastBlockHeight = req.InitialHeight
	app.logger.Info(fmt.Sprintf("COMETBFT Initialization End - INIT CHAIN"))
	return &types.InitChainResponse{Validators: app.valUpdates, AppHash: app.state.Hash()}, nil
}
