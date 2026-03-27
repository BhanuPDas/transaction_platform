package main

import (
	"github.com/cockroachdb/pebble/v2"
	"github.com/cometbft/cometbft/abci/types"
	"github.com/cometbft/cometbft/crypto"
	"github.com/cometbft/cometbft/libs/log"
)

type TransferTransaction struct {
	Type          string  `json:"type"`
	Buyer         string  `json:"buyer"`
	Seller        string  `json:"seller"`
	Amount        int64   `json:"amount"`
	Quantity      int64   `json:"quantity"`
	Score         float64 `json:"score"`
	Price         float64 `json:"price"`
	ResourceType  string  `json:"resource_type"`
	TxStartTs     string  `json:"tx_start_ts"`
	LeaseDuration int64   `json:"lease_duration"`
}

type Validators struct {
	Type      string          `json:"type"`
	Validator []ValidatorJSON `json:"validator"`
}

type ValidatorJSON struct {
	Power       int64  `json:"power"`
	PubKeyBytes string `json:"pub_key_bytes"`
	PubKeyType  string `json:"pub_key_type"`
}

type State struct {
	DB        *pebble.DB
	Size      int64                   `json:"size"`
	Height    int64                   `json:"height"`
	Ledger    map[string]int64        `json:"ledger"`
	Validator []types.ValidatorUpdate `json:"validator"`
}

type MyApp struct {
	types.BaseApplication
	state                      *State
	RetainBlocks               int64
	lastBlockHeight            int64
	valUpdates                 []types.ValidatorUpdate
	valAddrToPubKeyMap         map[string]crypto.PubKey
	updatedValidatorsThisBlock map[string]struct{}
	logger                     log.Logger
	cls                        []string
}

type TxDetails struct {
	Status  string
	TxHash  string
	TxEndTs string
	TxObj   TransferTransaction
	Log     string
}
