package main

import (
	"github.com/cockroachdb/pebble/v2"
	"github.com/cometbft/cometbft/abci/types"
	"github.com/cometbft/cometbft/crypto"
	"github.com/cometbft/cometbft/libs/log"
)

type SellerInfo struct {
	Name    string             `json:"name"`
	IP      string             `json:"ip"`
	CPU     int64              `json:"cpu"`
	RAM     float64            `json:"ram"`
	Storage int64              `json:"storage"`
	GPU     int64              `json:"gpu"`
	Price   map[string]float64 `json:"price"`
	Score   map[string]float64 `json:"score"`
}
type ResourceDemand struct {
	DemandPerUnit int64   `json:"demand_per_unit"`
	Score         float64 `json:"score"`
	Budget        float64 `json:"budget"`
}
type BuyerInfo struct {
	Name      string                    `json:"name"`
	IP        string                    `json:"ip"`
	Resources map[string]ResourceDemand `json:"resource"`
}
type TransferTransaction struct {
	Type          string     `json:"type"`
	Buyer         BuyerInfo  `json:"buyer"`
	Seller        SellerInfo `json:"seller"`
	Amount        int64      `json:"amount"`
	TxStartTs     string     `json:"tx_start_ts"`
	LeaseDuration int64      `json:"lease_duration"`
	SellerEnergy  float64    `json:"seller_energy"`
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
	State                      *State
	RetainBlocks               int64
	LastBlockHeight            int64
	ValUpdates                 []types.ValidatorUpdate
	ValAddrToPubKeyMap         map[string]crypto.PubKey
	UpdatedValidatorsThisBlock map[string]struct{}
	Logger                     log.Logger
	Cls                        []string
}

type TxDetails struct {
	Status    string
	TxHash    string
	TxEndUnix int64
	TxEndTs   string
	Tx        TransferTransaction
	Log       string
}
