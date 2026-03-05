package main

import (
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"github.com/cockroachdb/pebble/v2"
	"github.com/cometbft/cometbft/abci/types"
	"github.com/cometbft/cometbft/crypto"
	cryptoenc "github.com/cometbft/cometbft/crypto/encoding"
	"github.com/cometbft/cometbft/libs/log"
	"github.com/cometbft/cometbft/version"
	"sort"
	"strconv"
	"strings"
)

const (
	AppVersion          uint64 = 1
	TransferType               = "transfer"
	AddValidatorType           = "addval"
	RemoveValidatorType        = "remval"
	UpdateValidatorType        = "updval"
)

type TransferTransaction struct {
	Type      string `json:"type"`
	FromNode  string `json:"from_node"`
	ToNode    string `json:"to_node"`
	Amount    string `json:"amount"`
	Timestamp string `json:"timestamp"`
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
}

func NewMyApp(db *pebble.DB, logger log.Logger) *MyApp {
	app := &MyApp{
		state: &State{
			DB:        db,
			Ledger:    make(map[string]int64),
			Validator: make([]types.ValidatorUpdate, 0),
		},
		valAddrToPubKeyMap:         make(map[string]crypto.PubKey),
		logger:                     logger,
		updatedValidatorsThisBlock: make(map[string]struct{}),
	}
	app.logger.Info(fmt.Sprintf("Loading Data from DB..."))
	app.LoadFromDB()
	return app
}

func (app *MyApp) Info(ctx context.Context, req *types.InfoRequest) (*types.InfoResponse, error) {
	app.logger.Info(fmt.Sprintf("CometBFT Node connected. Version: %s, ABCIVersion: %s", req.Version, req.AbciVersion))
	return &types.InfoResponse{
		Version:          version.ABCIVersion,
		AppVersion:       AppVersion,
		LastBlockHeight:  app.state.Height,
		LastBlockAppHash: app.state.Hash(),
	}, nil
}

func (app *MyApp) InitChain(ctx context.Context, req *types.InitChainRequest) (*types.InitChainResponse, error) {
	app.logger.Info(fmt.Sprintf("COMETBFT Initialization Start - INIT CHAIN"))
	if len(app.state.Ledger) == 0 {
		app.logger.Info(fmt.Sprintf("No existing balances found, initializing defaults for all nodes..."))
		for i := 1; i <= 50; i++ {
			key := fmt.Sprintf("clab-century-serf%d", i)
			app.state.Ledger[key] = 10000
		}

	} else {
		app.logger.Info(fmt.Sprintf("Successfully restored balances from Pebble DB."))
	}
	app.logger.Info(fmt.Sprintf("Ledger initialized with %d accounts.", len(app.state.Ledger)))
	if len(app.state.Validator) == 0 {
		app.logger.Error(fmt.Sprintf("No validators found in DB...Add validators for consensus"))
	}
	app.logger.Info(fmt.Sprintf("Total validators initialized: %d", len(app.state.Validator)))
	app.lastBlockHeight = req.InitialHeight
	app.logger.Info(fmt.Sprintf("COMETBFT Initialization End - INIT CHAIN"))
	return &types.InitChainResponse{AppHash: app.state.Hash()}, nil
}

func (app *MyApp) CheckTx(ctx context.Context, req *types.CheckTxRequest) (*types.CheckTxResponse, error) {
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

func (app *MyApp) PrepareProposal(ctx context.Context, req *types.PrepareProposalRequest) (*types.PrepareProposalResponse, error) {
	return &types.PrepareProposalResponse{Txs: req.Txs}, nil
}

func (app *MyApp) ProcessProposal(ctx context.Context, req *types.ProcessProposalRequest) (*types.ProcessProposalResponse, error) {
	for _, tx := range req.Txs {
		resp, err := app.CheckTx(ctx, &types.CheckTxRequest{Tx: tx, Type: types.CHECK_TX_TYPE_CHECK})
		if err != nil {
			app.logger.Error(fmt.Sprintln("ProcessProposal: CheckTx call had an unrecoverable error", err))
		}
		if resp.Code != CodeTypeOK {
			return &types.ProcessProposalResponse{Status: types.PROCESS_PROPOSAL_STATUS_REJECT}, nil
		}
	}
	return &types.ProcessProposalResponse{Status: types.PROCESS_PROPOSAL_STATUS_ACCEPT}, nil
}

func (app *MyApp) FinalizeBlock(ctx context.Context, req *types.FinalizeBlockRequest) (*types.FinalizeBlockResponse, error) {
	app.logger.Info(fmt.Sprintf("=== [FINALIZE BLOCK START] (Block: %d) ===", req.Height))
	var meta struct {
		Type string `json:"type"`
	}
	app.valUpdates = make([]types.ValidatorUpdate, 0)
	app.updatedValidatorsThisBlock = make(map[string]struct{})

	//Punish Validators committing equivocation
	for _, ev := range req.Misbehavior {
		if ev.Type == types.MISBEHAVIOR_TYPE_DUPLICATE_VOTE {
			addr := string(ev.Validator.Address)
			pubKey, ok := app.valAddrToPubKeyMap[addr]
			if !ok {
				app.logger.Error(fmt.Sprintf("Address %q should be punished but address not found", addr))
				continue
			}
			power := ev.Validator.Power - 2
			if power < 0 {
				power = 0
			}
			update := types.ValidatorUpdate{
				Power:       power,
				PubKeyType:  pubKey.Type(),
				PubKeyBytes: pubKey.Bytes(),
			}
			app.appendValidatorUpdateOnce(addr, update)

			if power == 0 {
				app.removeFromStateValidator(addr)
			} else {
				app.addOrUpdateStateValidator(types.ValidatorUpdate{
					Power:       power,
					PubKeyType:  pubKey.Type(),
					PubKeyBytes: pubKey.Bytes(),
				}, addr)
			}
			app.logger.Info("Decreased validator power by 2 because of the equivocation", "val", addr)
		}
	}

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
			var tx TransferTransaction
			if err := json.Unmarshal(decodedStrTx, &tx); err != nil {
				txResults = append(txResults, &types.ExecTxResult{Code: 2, Log: "Bad JSON"})
				continue
			}
			amountStr := strings.TrimSuffix(tx.Amount, " tokens")
			amountInt, _ := strconv.ParseInt(amountStr, 10, 64)

			fromBalance := app.state.Ledger[tx.FromNode]
			if fromBalance < amountInt {
				txResults = append(txResults, &types.ExecTxResult{Code: 7, Log: "Insufficient funds"})
				continue
			}

			app.state.Ledger[tx.FromNode] -= amountInt
			app.state.Ledger[tx.ToNode] += amountInt
			txResults = append(txResults, &types.ExecTxResult{Code: 0, Log: "Executed"})
			app.state.Size++
		} else if meta.Type == AddValidatorType || meta.Type == RemoveValidatorType || meta.Type == UpdateValidatorType {
			var vtx Validators
			if err := json.Unmarshal(decodedStrTx, &vtx); err != nil {
				txResults = append(txResults, &types.ExecTxResult{Code: 2, Log: "Bad JSON"})
				continue
			}
			app.updateValidator(string(decodedStrTx))
			txResults = append(txResults, &types.ExecTxResult{Code: 0, Log: "Validator Request Executed"})
		}
	}
	app.lastBlockHeight = req.Height
	app.logger.Info(fmt.Sprintf("=== [FINALIZE BLOCK END] (Block: %d) ===", app.lastBlockHeight))
	return &types.FinalizeBlockResponse{TxResults: txResults, AppHash: app.state.Hash(), ValidatorUpdates: app.valUpdates}, nil
}

func (app *MyApp) Commit(ctx context.Context, req *types.CommitRequest) (*types.CommitResponse, error) {
	app.logger.Info(fmt.Sprintf("[Committing Transaction] (Block: %d) +++", app.lastBlockHeight))
	app.logger.Info(fmt.Sprintf("Persisting Transaction to DB"))
	app.SaveToDB()
	resp := &types.CommitResponse{}
	if app.RetainBlocks > 0 && app.state.Height >= app.RetainBlocks {
		resp.RetainHeight = app.state.Height - app.RetainBlocks + 1
	}
	return resp, nil
}

// add, update, or remove a validator.
func (app *MyApp) updateValidator(vReqTx string) {
	var vtx Validators
	if err := json.Unmarshal([]byte(vReqTx), &vtx); err != nil {
		app.logger.Error(fmt.Sprintf("Error unmarshalling validator tx json: %v", err))
		return
	}
	tp := vtx.Type
	for _, val := range vtx.Validator {
		pubKeyBytes, err := base64.StdEncoding.DecodeString(val.PubKeyBytes)
		if err != nil {
			app.logger.Error("PubKey decode error:", "err", err)
			continue
		}
		pubkey, err := cryptoenc.PubKeyFromTypeAndBytes(val.PubKeyType, pubKeyBytes)
		if err != nil {
			app.logger.Error("PubKey Error:", "err", err)
		}
		addr := string(pubkey.Address())
		switch tp {
		case RemoveValidatorType:
			removeUpdate := types.ValidatorUpdate{
				PubKeyType:  val.PubKeyType,
				PubKeyBytes: pubKeyBytes,
				Power:       0,
			}
			if _, ok := app.valAddrToPubKeyMap[addr]; !ok {
				app.logger.Error("Attempt to remove non-existent validator", "addr", addr)
				continue
			}
			app.appendValidatorUpdateOnce(addr, removeUpdate)
			app.removeFromStateValidator(addr)
			delete(app.valAddrToPubKeyMap, addr)

		case AddValidatorType, UpdateValidatorType:
			app.valAddrToPubKeyMap[addr] = pubkey
			app.addOrUpdateStateValidator(types.ValidatorUpdate{
				PubKeyType:  val.PubKeyType, // 🔹 UPDATED
				PubKeyBytes: pubKeyBytes,    // 🔹 UPDATED
				Power:       val.Power,
			}, addr)
			app.appendValidatorUpdateOnce(addr, types.ValidatorUpdate{
				PubKeyType:  val.PubKeyType,
				PubKeyBytes: pubKeyBytes,
				Power:       val.Power,
			})

		default:
			app.logger.Error(fmt.Sprintf("Unknown validator update type: %s", tp))
			return
		}
	}
	app.sortStateValidatorByAddress()
}

func (app *MyApp) addOrUpdateStateValidator(v types.ValidatorUpdate, addr string) {
	// update if exists
	for i, existing := range app.state.Validator {
		pub, _ := cryptoenc.PubKeyFromTypeAndBytes(existing.PubKeyType, existing.PubKeyBytes)
		if string(pub.Address()) == addr {
			app.state.Validator[i] = v
			return
		}
	}
	app.state.Validator = append(app.state.Validator, v)
}

func (app *MyApp) removeFromStateValidator(addr string) {
	newList := make([]types.ValidatorUpdate, 0, len(app.state.Validator))
	for _, existing := range app.state.Validator {
		pub, _ := cryptoenc.PubKeyFromTypeAndBytes(existing.PubKeyType, existing.PubKeyBytes)
		if string(pub.Address()) != addr {
			newList = append(newList, existing)
		}
	}
	app.state.Validator = newList
}

func (app *MyApp) sortStateValidatorByAddress() {
	sort.Slice(app.state.Validator, func(i, j int) bool {
		pub1, _ := cryptoenc.PubKeyFromTypeAndBytes(app.state.Validator[i].PubKeyType, app.state.Validator[i].PubKeyBytes)
		pub2, _ := cryptoenc.PubKeyFromTypeAndBytes(app.state.Validator[j].PubKeyType, app.state.Validator[j].PubKeyBytes)

		return string(pub1.Address()) < string(pub2.Address())
	})
}

func (s *State) Hash() []byte {
	ledgerKeys := make([]string, 0, len(s.Ledger))
	for k := range s.Ledger {
		ledgerKeys = append(ledgerKeys, k)
	}
	sort.Strings(ledgerKeys)
	sortedLedger := make(map[string]int64, len(s.Ledger))
	for _, k := range ledgerKeys {
		sortedLedger[k] = s.Ledger[k]
	}
	canonical := map[string]interface{}{
		"height":    s.Height,
		"size":      s.Size,
		"ledger":    sortedLedger,
		"validator": s.Validator,
	}
	data, _ := json.Marshal(canonical)
	h := sha256.Sum256(data)
	return h[:]
}

// LoadFromDB loads current state from PebbleDB into memory.
func (app *MyApp) LoadFromDB() {
	iter, err := app.state.DB.NewIter(&pebble.IterOptions{LowerBound: []byte("balance:"), UpperBound: []byte("balance~")})
	if err != nil {
		panic(fmt.Sprintf("Failed to Iterate Balance Records: %v", err))
		return
	}
	defer func(iter *pebble.Iterator) {
		err := iter.Close()
		if err != nil {
			panic(fmt.Sprintf("Failed to close Balance iterator: %v", err))
		}
	}(iter)
	count := 0
	for iter.First(); iter.Valid(); iter.Next() {
		key := string(iter.Key())
		if strings.HasPrefix(key, "balance:") {
			node := strings.TrimPrefix(key, "balance:")
			valStr1, err := iter.ValueAndErr()
			if err != nil {
				app.logger.Error(fmt.Sprintf("Error getting balance: %v", err))
				continue
			}
			valStr := string(valStr1)
			val, err := strconv.ParseInt(valStr, 10, 64)
			if err != nil {
				app.logger.Error(fmt.Sprintf("Skipping invalid value for %s: %s", node, valStr))
				continue
			}
			app.state.Ledger[node] = val
			count++
		}
	}
	if err := iter.Error(); err != nil {
		panic(fmt.Sprintf("DB Iterator encountered an error: %v", err))
	}
	app.logger.Info(fmt.Sprintf("Loaded %d balances from Pebble DB: %+v", count, app.state.Ledger))
	iter2, err := app.state.DB.NewIter(&pebble.IterOptions{
		LowerBound: []byte("validator:"),
		UpperBound: []byte("validator~"),
	})
	if err != nil {
		panic(fmt.Sprintf("Failed to create validator records: %v", err))
		return
	}
	defer func(iter2 *pebble.Iterator) {
		err := iter2.Close()
		if err != nil {
			panic(fmt.Sprintf("Failed to validator close iterator: %v", err))
		}
	}(iter2)
	validatorCount := 0
	for iter2.First(); iter2.Valid(); iter2.Next() {
		key := string(iter2.Key())
		if strings.HasPrefix(key, "validator:") {
			id := strings.TrimPrefix(key, "validator:")
			valBytes, err := iter2.ValueAndErr()
			if err != nil {
				app.logger.Error(fmt.Sprintf("Error getting validator: %v", err))
			}
			var vu types.ValidatorUpdate
			err = json.Unmarshal(valBytes, &vu)
			if err != nil {
				app.logger.Error(fmt.Sprintf("Failed to deserialize validator %s: %v", id, err))
				continue
			}
			pubKeyBytes := vu.PubKeyBytes
			app.state.Validator = append(app.state.Validator, vu)
			pubkey, err := cryptoenc.PubKeyFromTypeAndBytes(vu.PubKeyType, pubKeyBytes)
			if err != nil {
				panic(fmt.Sprintf("Failed to decode validator pubkey: %v", err))
			}
			addr := string(pubkey.Address())
			app.valAddrToPubKeyMap[addr] = pubkey
			validatorCount++
		}
	}

	app.logger.Info(fmt.Sprintf("Loaded %d validators from PebbleDB", validatorCount))
}

// SaveToDB persists the current state to Pebble DB.
func (app *MyApp) SaveToDB() {
	for node, balance := range app.state.Ledger {
		key := "balance:" + node
		val := []byte(fmt.Sprintf("%d", balance))
		if err := app.state.DB.Set([]byte(key), val, pebble.Sync); err != nil {
			panic(fmt.Sprintf("Failed to persist %s: %v\n", node, err))
		}
	}
	app.logger.Info(fmt.Sprintf("[SAVE] Balances successfully persisted to Blockchain PebbleDB."))
	for _, valUpdate := range app.state.Validator {
		pubKeyBytes := valUpdate.PubKeyBytes
		pubkey, err := cryptoenc.PubKeyFromTypeAndBytes(valUpdate.PubKeyType, pubKeyBytes)
		if err != nil {
			panic(err)
		}
		key := "validator:" + string(pubkey.Address())
		jsonBytes, err := json.Marshal(valUpdate)
		if err != nil {
			app.logger.Error(fmt.Sprintf("Failed to serialize validator %s: %v", key, err))
			continue
		}
		if err := app.state.DB.Set([]byte(key), jsonBytes, pebble.Sync); err != nil {
			panic(fmt.Sprintf("Failed to persist validator %s: %v", key, err))
		}
	}

	app.logger.Info(fmt.Sprintf("Validators successfully persisted to PebbleDB."))
}

func (app *MyApp) CheckTransferTX(reqtx string) (*types.CheckTxResponse, error) {
	var tx TransferTransaction
	if err := json.Unmarshal([]byte(reqtx), &tx); err != nil {
		msg := fmt.Sprintf("ERROR: Failed to parse JSON: %v", err)
		return &types.CheckTxResponse{Code: 2, Log: msg}, nil
	}
	if tx.Type == "" || tx.FromNode == "" || tx.ToNode == "" || tx.Amount == "" || tx.Timestamp == "" {
		logMsg := "ABCI CheckTx ERROR: Missing one or more required fields (type, from_node, to_node, amount, timestamp)."
		app.logger.Error(logMsg)
		return &types.CheckTxResponse{Code: 4, Log: logMsg}, nil
	}

	amountStr := strings.TrimSuffix(tx.Amount, " tokens")
	amountInt, err := strconv.ParseInt(amountStr, 10, 64)
	if err != nil {
		msg := fmt.Sprintf("ERROR: Invalid amount: %s", tx.Amount)
		return &types.CheckTxResponse{Code: 5, Log: msg}, nil
	}

	fromBalance, ok := app.state.Ledger[tx.FromNode]
	if !ok {
		return &types.CheckTxResponse{Code: 6, Log: fmt.Sprintf(" Error: 'from' node '%s' missing", tx.FromNode)}, nil
	}
	if fromBalance < amountInt {
		msg := fmt.Sprintf("ERROR: Insufficient funds for '%s'. Has %d, needs %d",
			tx.FromNode, fromBalance, amountInt)
		return &types.CheckTxResponse{Code: 7, Log: msg}, nil
	}

	app.logger.Info(fmt.Sprintf("Transaction OK. From=%s, To=%s, Amount=%d", tx.FromNode, tx.ToNode, amountInt))
	return &types.CheckTxResponse{Code: 0, Log: "Transaction format and logic OK."}, nil
}

func (app *MyApp) CheckValidatorTX(reqtx string) (*types.CheckTxResponse, error) {
	var tx Validators
	if err := json.Unmarshal([]byte(reqtx), &tx); err != nil {
		msg := fmt.Sprintf("ERROR: Failed to parse JSON: %v", err)
		return &types.CheckTxResponse{Code: 2, Log: msg}, nil
	}
	if len(tx.Validator) == 0 {
		logMsg := "ABCI CheckTx ERROR: Missing one or more required fields (type, Validator)."
		app.logger.Error(logMsg)
		return &types.CheckTxResponse{Code: 4, Log: logMsg}, nil
	}
	for _, v := range tx.Validator {
		if v.Power < 0 {
			return &types.CheckTxResponse{Code: 5, Log: "Validator power cannot be negative"}, nil
		}
	}

	app.logger.Info(fmt.Sprintf("Validator Transaction OK."))
	return &types.CheckTxResponse{Code: 0, Log: "Validator Transaction Check passed."}, nil
}

func (app *MyApp) appendValidatorUpdateOnce(addr string, vu types.ValidatorUpdate) {
	if _, seen := app.updatedValidatorsThisBlock[addr]; seen {
		app.logger.Info("Skipping duplicate validator update in same block", "addr", addr)
		return
	}
	app.updatedValidatorsThisBlock[addr] = struct{}{}
	app.valUpdates = append(app.valUpdates, vu)
}
