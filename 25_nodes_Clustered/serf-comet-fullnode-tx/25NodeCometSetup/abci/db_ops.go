package main

import (
	"encoding/json"
	"fmt"
	"github.com/cockroachdb/pebble/v2"
	"github.com/cometbft/cometbft/abci/types"
	cryptoenc "github.com/cometbft/cometbft/crypto/encoding"
	"strconv"
	"strings"
	"time"
)

// LoadFromDB loads current State from PebbleDB into memory.
func (app *MyApp) LoadFromDB() {
	iter, err := app.State.DB.NewIter(&pebble.IterOptions{LowerBound: []byte("balance:"), UpperBound: []byte("balance~")})
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
				app.Logger.Error(fmt.Sprintf("Error getting balance: %v", err))
				continue
			}
			valStr := string(valStr1)
			val, err := strconv.ParseInt(valStr, 10, 64)
			if err != nil {
				app.Logger.Error(fmt.Sprintf("Skipping invalid value for %s: %s", node, valStr))
				continue
			}
			app.State.Ledger[node] = val
			count++
		}
	}
	if err := iter.Error(); err != nil {
		panic(fmt.Sprintf("DB Iterator encountered an error: %v", err))
	}
	app.Logger.Info(fmt.Sprintf("Loaded %d balances from Pebble DB: %+v", count, app.State.Ledger))
	iter2, err := app.State.DB.NewIter(&pebble.IterOptions{
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
				app.Logger.Error(fmt.Sprintf("Error getting validator: %v", err))
			}
			var vu types.ValidatorUpdate
			err = json.Unmarshal(valBytes, &vu)
			if err != nil {
				app.Logger.Error(fmt.Sprintf("Failed to deserialize validator %s: %v", id, err))
				continue
			}
			pubKeyBytes := vu.PubKeyBytes
			app.State.Validator = append(app.State.Validator, vu)
			pubkey, err := cryptoenc.PubKeyFromTypeAndBytes(vu.PubKeyType, pubKeyBytes)
			if err != nil {
				panic(fmt.Sprintf("Failed to decode validator pubkey: %v", err))
			}
			addr := string(pubkey.Address())
			app.ValAddrToPubKeyMap[addr] = pubkey
			validatorCount++
		}
	}

	app.Logger.Info(fmt.Sprintf("Loaded %d validators from PebbleDB", validatorCount))
}

// SaveToDB persists the current State to Pebble DB.
func (app *MyApp) SaveToDB() {
	for node, balance := range app.State.Ledger {
		key := "balance:" + node
		val := []byte(fmt.Sprintf("%d", balance))
		if err := app.State.DB.Set([]byte(key), val, pebble.Sync); err != nil {
			panic(fmt.Sprintf("Failed to persist %s: %v\n", node, err))
		}
	}
	app.Logger.Info(fmt.Sprintf("[SAVE] Balances successfully persisted to Blockchain PebbleDB."))
	for _, valUpdate := range app.State.Validator {
		pubKeyBytes := valUpdate.PubKeyBytes
		pubkey, err := cryptoenc.PubKeyFromTypeAndBytes(valUpdate.PubKeyType, pubKeyBytes)
		if err != nil {
			panic(err)
		}
		key := "validator:" + string(pubkey.Address())
		jsonBytes, err := json.Marshal(valUpdate)
		if err != nil {
			app.Logger.Error(fmt.Sprintf("Failed to serialize validator %s: %v", key, err))
			continue
		}
		if err := app.State.DB.Set([]byte(key), jsonBytes, pebble.Sync); err != nil {
			panic(fmt.Sprintf("Failed to persist validator %s: %v", key, err))
		}
	}

	app.Logger.Info(fmt.Sprintf("Validators successfully persisted to PebbleDB."))
}

func getBucket(ts time.Time) string {
	return ts.Truncate(10 * time.Minute).Format(time.RFC3339)
}

func (app *MyApp) SaveTx(txHash string, txDetails TxDetails, endTime time.Time) {
	txKey := "tx:" + txHash
	txBytes, _ := json.Marshal(txDetails)
	if err := app.State.DB.Set([]byte(txKey), txBytes, pebble.Sync); err != nil {
		app.Logger.Error(fmt.Sprintf("DB write failed: %v", err))
	}
	// Store bucket index for future re-check
	bucket := getBucket(endTime)
	bucketKey := fmt.Sprintf("bucket:%s:%s", bucket, txHash)

	if err := app.State.DB.Set([]byte(bucketKey), []byte(txHash), pebble.Sync); err != nil {
		app.Logger.Error(fmt.Sprintf("Bucket write failed: %v", err))
	}
}

func (app *MyApp) ProcessExpiredTxs(req *types.FinalizeBlockRequest) {
	now := req.Time.UTC()
	iter, err := app.State.DB.NewIter(&pebble.IterOptions{
		LowerBound: []byte("tx:"),
		UpperBound: []byte("tx~"),
	})
	if err != nil {
		panic(err)
	}
	defer func(iter *pebble.Iterator) {
		err := iter.Close()
		if err != nil {
			panic(fmt.Sprintf("Failed to close iterator: %v", err))
		}
	}(iter)

	for iter.First(); iter.Valid(); iter.Next() {
		key := string(iter.Key())
		val, err := iter.ValueAndErr()
		if err != nil {
			continue
		}
		valBytes := append([]byte{}, val...)
		var txDetails TxDetails
		if err := json.Unmarshal(valBytes, &txDetails); err != nil {
			continue
		}

		if txDetails.Status != StatusOnGoing {
			continue
		}

		if now.Unix() >= txDetails.TxEndUnix {
			app.Logger.Info("EXPIRING TX", "txHash", txDetails.TxHash,
				"now", now.Unix(), "end", txDetails.TxEndUnix,
			)
			txDetails.Status = StatusCompleted
			txDetails.TxEndTs = now.Format(time.RFC3339Nano)
			txDetails.Log = "Transaction Completed"
			updatedBytes, _ := json.Marshal(txDetails)
			if err := app.State.DB.Set([]byte(key), updatedBytes, pebble.Sync); err != nil {
				app.Logger.Error(fmt.Sprintf("Failed to update tx: %v", err))
			}
		}
	}
	if err := iter.Error(); err != nil {
		panic(err)
	}
}

func (app *MyApp) FetchTxs() []TxDetails {
	var transactions []TxDetails
	iter, err := app.State.DB.NewIter(&pebble.IterOptions{
		LowerBound: []byte("tx:"),
		UpperBound: []byte("tx~"),
	})
	if err != nil {
		app.Logger.Error(fmt.Sprintf("Failed to open iterator while fetching tx records: %v", err))
	}
	defer func() {
		if err := iter.Close(); err != nil {
			app.Logger.Error(fmt.Sprintf("Failed to close iterator: %v", err))
		}
	}()
	for iter.First(); iter.Valid(); iter.Next() {
		val, err := iter.ValueAndErr()
		if err != nil {
			app.Logger.Error(fmt.Sprintf("Failed to read value: %v", err))
			continue
		}
		valBytes := append([]byte{}, val...)
		var tx TxDetails
		if err := json.Unmarshal(valBytes, &tx); err != nil {
			app.Logger.Error(fmt.Sprintf("Failed to unmarshal tx: %v", err))
			continue
		}
		transactions = append(transactions, tx)
	}

	if err := iter.Error(); err != nil {
		app.Logger.Error(fmt.Sprintf("Failed to close iterator: %v", err))
	}
	return transactions
}
