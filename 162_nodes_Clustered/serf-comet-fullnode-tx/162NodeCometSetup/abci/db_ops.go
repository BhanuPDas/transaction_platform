package main

import (
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/cockroachdb/pebble/v2"
	"github.com/cometbft/cometbft/abci/types"
	cryptoenc "github.com/cometbft/cometbft/crypto/encoding"
)

const (
	fetchTxWindowSeconds = 15 * 60 // 15 minutes in seconds
)

// LoadFromDB loads current State from PebbleDB into memory.
func (app *MyApp) LoadFromDB() {
	const balancePrefix = "balance:"
	balanceIter, err := app.State.DB.NewIter(&pebble.IterOptions{
		LowerBound: []byte(balancePrefix),
		UpperBound: []byte("balance~"), // '~' (0x7E) > any printable char after ':'
	})
	if err != nil {
		app.Logger.Error(fmt.Sprintf("LoadFromDB: failed to create balance iterator: %v", err))
		return
	}
	defer func() {
		if err := balanceIter.Close(); err != nil {
			app.Logger.Error(fmt.Sprintf("LoadFromDB: failed to close balance iterator: %v", err))
		}
	}()

	balanceCount := 0
	for balanceIter.First(); balanceIter.Valid(); balanceIter.Next() {
		node := string(balanceIter.Key()[len(balancePrefix):])

		valBytes, err := balanceIter.ValueAndErr()
		if err != nil {
			app.Logger.Error(fmt.Sprintf("LoadFromDB: failed to read balance value for %s: %v", node, err))
			continue
		}

		val, err := strconv.ParseInt(strings.TrimSpace(string(valBytes)), 10, 64)
		if err != nil {
			app.Logger.Error(fmt.Sprintf("LoadFromDB: skipping invalid balance for %s: %q", node, string(valBytes)))
			continue
		}

		app.State.Ledger[node] = val
		balanceCount++
	}
	if err := balanceIter.Error(); err != nil {
		app.Logger.Error(fmt.Sprintf("LoadFromDB: balance iterator error: %v", err))
	}
	app.Logger.Info(fmt.Sprintf("LoadFromDB: loaded %d balances: %+v", balanceCount, app.State.Ledger))

	const validatorPrefix = "validator:"
	validatorIter, err := app.State.DB.NewIter(&pebble.IterOptions{
		LowerBound: []byte(validatorPrefix),
		UpperBound: []byte("validator~"),
	})
	if err != nil {
		app.Logger.Error(fmt.Sprintf("LoadFromDB: failed to create validator iterator: %v", err))
		return
	}
	defer func() {
		if err := validatorIter.Close(); err != nil {
			app.Logger.Error(fmt.Sprintf("LoadFromDB: failed to close validator iterator: %v", err))
		}
	}()

	validatorCount := 0
	for validatorIter.First(); validatorIter.Valid(); validatorIter.Next() {
		id := string(validatorIter.Key()[len(validatorPrefix):])

		valBytes, err := validatorIter.ValueAndErr()
		if err != nil {
			app.Logger.Error(fmt.Sprintf("LoadFromDB: failed to read validator value for %s: %v", id, err))
			continue
		}
		valCopy := append([]byte{}, valBytes...)
		var vu types.ValidatorUpdate
		if err := json.Unmarshal(valCopy, &vu); err != nil {
			app.Logger.Error(fmt.Sprintf("LoadFromDB: failed to deserialize validator %s: %v", id, err))
			continue
		}

		app.State.Validator = append(app.State.Validator, vu)

		pubkey, err := cryptoenc.PubKeyFromTypeAndBytes(vu.PubKeyType, vu.PubKeyBytes)
		if err != nil {
			app.Logger.Error(fmt.Sprintf("LoadFromDB: failed to decode pubkey for validator %s: %v", id, err))
			continue
		}

		app.ValAddrToPubKeyMap[string(pubkey.Address())] = pubkey
		validatorCount++
	}
	if err := validatorIter.Error(); err != nil {
		app.Logger.Error(fmt.Sprintf("LoadFromDB: validator iterator error: %v", err))
	}
	app.Logger.Info(fmt.Sprintf("LoadFromDB: loaded %d validators", validatorCount))
}

// SaveToDB persists balances and validators to PebbleDB.
func (app *MyApp) SaveToDB() {
	batch := app.State.DB.NewBatch()
	defer func() {
		if err := batch.Close(); err != nil {
			app.Logger.Error(fmt.Sprintf("SaveToDB: failed to close batch: %v", err))
		}
	}()

	batchErr := false
	balanceCount := 0
	for node, balance := range app.State.Ledger {
		key := "balance:" + node
		val := strconv.AppendInt(nil, balance, 10) // allocation-free int64 → []byte
		if err := batch.Set([]byte(key), val, nil); err != nil {
			app.Logger.Error(fmt.Sprintf("SaveToDB: batch.Set balance failed for %s: %v", node, err))
			batchErr = true
			break
		}
		balanceCount++
	}
	if batchErr {
		app.Logger.Error("SaveToDB: aborting batch due to balance write error")
		return
	}

	validatorCount := 0
	if app.ValidatorsDirty {
		for _, valUpdate := range app.State.Validator {
			pubkey, err := cryptoenc.PubKeyFromTypeAndBytes(valUpdate.PubKeyType, valUpdate.PubKeyBytes)
			if err != nil {
				app.Logger.Error(fmt.Sprintf("SaveToDB: failed to decode pubkey, skipping validator: %v", err))
				continue
			}
			key := "validator:" + string(pubkey.Address())
			jsonBytes, err := json.Marshal(valUpdate)
			if err != nil {
				app.Logger.Error(fmt.Sprintf("SaveToDB: failed to serialize validator %s: %v", key, err))
				continue
			}
			if err := batch.Set([]byte(key), jsonBytes, nil); err != nil {
				app.Logger.Error(fmt.Sprintf("SaveToDB: batch.Set validator failed for %s: %v", key, err))
				batchErr = true
				break
			}
			validatorCount++
		}
		if batchErr {
			app.Logger.Error("SaveToDB: aborting batch due to validator write error")
			return
		}
	}

	if err := batch.Commit(pebble.Sync); err != nil {
		app.Logger.Error(fmt.Sprintf("SaveToDB: batch commit failed: %v", err))
		return
	}

	if app.ValidatorsDirty {
		app.ValidatorsDirty = false
	}

	app.Logger.Info(fmt.Sprintf(
		"SaveToDB: persisted %d balances, %d validators (single fsync, validatorsDirty was %v)",
		balanceCount, validatorCount, validatorCount > 0,
	))
}

// getBucket returns a 10-minute truncated RFC3339 UTC timestamp string.
func getBucket(ts time.Time) string {
	return ts.UTC().Truncate(10 * time.Minute).Format(time.RFC3339)
}

// bucketKey constructs the canonical bucket index key.
func bucketKey(endTime time.Time, txHash string) string {
	return fmt.Sprintf("bucket:%s:%s", getBucket(endTime), txHash)
}

// SaveTx persists a transaction record and its bucket index entry atomically
// using a PebbleDB batch. Both writes succeed or both fail — no partial state.
func (app *MyApp) SaveTx(txHash string, txDetails TxDetails, endTime time.Time) {
	txBytes, err := json.Marshal(txDetails)
	if err != nil {
		app.Logger.Error(fmt.Sprintf("SaveTx: failed to marshal txDetails for %s: %v", txHash, err))
		return
	}

	batch := app.State.DB.NewBatch()
	defer func() {
		if err := batch.Close(); err != nil {
			app.Logger.Error(fmt.Sprintf("SaveTx: failed to close batch for %s: %v", txHash, err))
		}
	}()

	txKey := "tx:" + txHash
	if err := batch.Set([]byte(txKey), txBytes, pebble.Sync); err != nil {
		app.Logger.Error(fmt.Sprintf("SaveTx: batch.Set tx key failed for %s: %v", txHash, err))
		return
	}

	bKey := bucketKey(endTime, txHash)
	if err := batch.Set([]byte(bKey), []byte(txHash), pebble.Sync); err != nil {
		app.Logger.Error(fmt.Sprintf("SaveTx: batch.Set bucket key failed for %s: %v", txHash, err))
		return
	}

	if err := batch.Commit(pebble.Sync); err != nil {
		app.Logger.Error(fmt.Sprintf("SaveTx: batch commit failed for %s: %v", txHash, err))
	}
}

// deleteBucketEntry removes the bucket index key for a given txHash and endTime.
func (app *MyApp) deleteBucketEntry(txHash string, txEndUnix int64) {
	endTime := time.Unix(txEndUnix, 0).UTC()
	bKey := bucketKey(endTime, txHash)
	if err := app.State.DB.Delete([]byte(bKey), pebble.Sync); err != nil {
		app.Logger.Error(fmt.Sprintf("deleteBucketEntry: failed to delete bucket key %s: %v", bKey, err))
	}
}

// ProcessExpiredTxs scans only bucket index keys whose 10-minute window has
// elapsed (upper bound = current window), does a point lookup per candidate
// txHash, and marks qualifying StatusOnGoing transactions as StatusCompleted.
// After marking a TX complete, the bucket entry is deleted so it is never
// visited again.
func (app *MyApp) ProcessExpiredTxs(req *types.FinalizeBlockRequest) {
	now := req.Time.UTC()

	upperBound := fmt.Sprintf("bucket:%s~", getBucket(now))

	iter, err := app.State.DB.NewIter(&pebble.IterOptions{
		LowerBound: []byte("bucket:"),
		UpperBound: []byte(upperBound),
	})
	if err != nil {
		app.Logger.Error(fmt.Sprintf("ProcessExpiredTxs: failed to create iterator: %v", err))
		return
	}
	defer func(iter *pebble.Iterator) {
		if err := iter.Close(); err != nil {
			app.Logger.Error(fmt.Sprintf("ProcessExpiredTxs: failed to close iterator: %v", err))
		}
	}(iter)

	for iter.First(); iter.Valid(); iter.Next() {
		val, err := iter.ValueAndErr()
		if err != nil {
			app.Logger.Error(fmt.Sprintf("ProcessExpiredTxs: failed to read bucket value: %v", err))
			continue
		}
		txHash := string(append([]byte{}, val...))
		txKey := "tx:" + txHash

		txBytes, closer, err := app.State.DB.Get([]byte(txKey))
		if err != nil {
			app.Logger.Error(fmt.Sprintf(
				"ProcessExpiredTxs: tx record missing for hash %s (stale bucket entry), cleaning up: %v",
				txHash, err,
			))
			bucketKeyStr := string(iter.Key())
			if delErr := app.State.DB.Delete([]byte(bucketKeyStr), pebble.Sync); delErr != nil {
				app.Logger.Error(fmt.Sprintf("ProcessExpiredTxs: failed to delete stale bucket key %s: %v", bucketKeyStr, delErr))
			}
			continue
		}
		txData := append([]byte{}, txBytes...)
		_ = closer.Close()

		var txDetails TxDetails
		if err := json.Unmarshal(txData, &txDetails); err != nil {
			app.Logger.Error(fmt.Sprintf("ProcessExpiredTxs: failed to unmarshal tx %s: %v", txHash, err))
			continue
		}

		if txDetails.Status != StatusOnGoing {
			app.Logger.Info(fmt.Sprintf(
				"ProcessExpiredTxs: tx %s already in terminal status %s, cleaning up stale bucket entry",
				txHash, txDetails.Status,
			))
			bucketKeyStr := string(iter.Key())
			if delErr := app.State.DB.Delete([]byte(bucketKeyStr), pebble.Sync); delErr != nil {
				app.Logger.Error(fmt.Sprintf("ProcessExpiredTxs: failed to delete stale bucket key %s: %v", bucketKeyStr, delErr))
			}
			continue
		}

		if now.Unix() < txDetails.TxEndUnix {
			continue
		}

		app.Logger.Info("ProcessExpiredTxs: expiring tx",
			"txHash", txDetails.TxHash,
			"now", now.Unix(),
			"end", txDetails.TxEndUnix,
		)

		txDetails.Status = StatusCompleted
		txDetails.TxEndTs = now.Format(time.RFC3339Nano)
		txDetails.Log = "Transaction Completed"

		updatedBytes, err := json.Marshal(txDetails)
		if err != nil {
			app.Logger.Error(fmt.Sprintf("ProcessExpiredTxs: failed to marshal updated tx %s: %v", txHash, err))
			continue
		}

		batch := app.State.DB.NewBatch()
		batchOk := true

		if err := batch.Set([]byte(txKey), updatedBytes, pebble.Sync); err != nil {
			app.Logger.Error(fmt.Sprintf("ProcessExpiredTxs: batch.Set failed for tx %s: %v", txHash, err))
			batchOk = false
		}

		bucketKeyStr := string(iter.Key())
		if batchOk {
			if err := batch.Delete([]byte(bucketKeyStr), pebble.Sync); err != nil {
				app.Logger.Error(fmt.Sprintf("ProcessExpiredTxs: batch.Delete failed for bucket key %s: %v", bucketKeyStr, err))
				batchOk = false
			}
		}

		if batchOk {
			if err := batch.Commit(pebble.Sync); err != nil {
				app.Logger.Error(fmt.Sprintf("ProcessExpiredTxs: batch commit failed for tx %s: %v", txHash, err))
			}
		}

		if err := batch.Close(); err != nil {
			app.Logger.Error(fmt.Sprintf("ProcessExpiredTxs: batch.Close failed for tx %s: %v", txHash, err))
		}
	}

	if err := iter.Error(); err != nil {
		app.Logger.Error(fmt.Sprintf("ProcessExpiredTxs: iterator error: %v", err))
	}
}

// FetchTxs returns transaction records whose
// TxEndUnix falls within the last fetchTxWindowSeconds (15 minutes).
func (app *MyApp) FetchTxs() []TxDetails {
	var transactions []TxDetails

	cutoff := time.Now().UTC().Unix() - fetchTxWindowSeconds

	iter, err := app.State.DB.NewIter(&pebble.IterOptions{
		LowerBound: []byte("tx:"),
		UpperBound: []byte("tx~"),
	})
	if err != nil {
		app.Logger.Error(fmt.Sprintf("FetchTxs: failed to open iterator: %v", err))
		return transactions
	}
	defer func() {
		if err := iter.Close(); err != nil {
			app.Logger.Error(fmt.Sprintf("FetchTxs: failed to close iterator: %v", err))
		}
	}()

	for iter.First(); iter.Valid(); iter.Next() {
		val, err := iter.ValueAndErr()
		if err != nil {
			app.Logger.Error(fmt.Sprintf("FetchTxs: failed to read value: %v", err))
			continue
		}
		valBytes := append([]byte{}, val...)

		var tx TxDetails
		if err := json.Unmarshal(valBytes, &tx); err != nil {
			app.Logger.Error(fmt.Sprintf("FetchTxs: failed to unmarshal tx: %v", err))
			continue
		}
		if tx.TxEndUnix >= cutoff {
			transactions = append(transactions, tx)
		}
	}

	if err := iter.Error(); err != nil {
		app.Logger.Error(fmt.Sprintf("FetchTxs: iterator error: %v", err))
	}

	app.Logger.Info(fmt.Sprintf("FetchTxs: returned %d transactions (cutoff unix=%d)", len(transactions), cutoff))
	return transactions
}

func (app *MyApp) FetchTxsHistory() []TxDetails {
	var transactions []TxDetails

	iter, err := app.State.DB.NewIter(&pebble.IterOptions{
		LowerBound: []byte("tx:"),
		UpperBound: []byte("tx~"),
	})
	if err != nil {
		app.Logger.Error(fmt.Sprintf("FetchTxs: failed to open iterator: %v", err))
		return transactions
	}
	defer func() {
		if err := iter.Close(); err != nil {
			app.Logger.Error(fmt.Sprintf("FetchTxs: failed to close iterator: %v", err))
		}
	}()

	for iter.First(); iter.Valid(); iter.Next() {
		val, err := iter.ValueAndErr()
		if err != nil {
			app.Logger.Error(fmt.Sprintf("FetchTxs: failed to read value: %v", err))
			continue
		}
		valBytes := append([]byte{}, val...)

		var tx TxDetails
		if err := json.Unmarshal(valBytes, &tx); err != nil {
			app.Logger.Error(fmt.Sprintf("FetchTxs: failed to unmarshal tx: %v", err))
			continue
		}
		transactions = append(transactions, tx)
	}

	if err := iter.Error(); err != nil {
		app.Logger.Error(fmt.Sprintf("FetchTxs: iterator error: %v", err))
	}

	app.Logger.Info(fmt.Sprintf("FetchTxs: returned %d transactions: ", len(transactions)))
	return transactions
}
