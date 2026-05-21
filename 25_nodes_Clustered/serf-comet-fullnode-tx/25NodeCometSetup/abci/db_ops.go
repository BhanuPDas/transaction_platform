package main

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/cockroachdb/pebble/v2"
	"github.com/cometbft/cometbft/abci/types"
	cryptoenc "github.com/cometbft/cometbft/crypto/encoding"
	"strconv"
	"strings"
)

const (
	fetchTxWindowSeconds = 15 * 60 // 15 minutes in seconds
)

// LoadFromDB loads current State from PebbleDB into memory.
func (app *MyApp) LoadFromDB() {
	iter, err := app.State.DB.NewIter(&pebble.IterOptions{
		LowerBound: []byte("balance:"),
		UpperBound: []byte("balance~"),
	})
	if err != nil {
		app.Logger.Error(fmt.Sprintf("Failed to Iterate Balance Records: %v", err))
	}
	defer func(iter *pebble.Iterator) {
		if err := iter.Close(); err != nil {
			app.Logger.Error(fmt.Sprintf("Failed to close Balance iterator: %v", err))
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
		app.Logger.Error(fmt.Sprintf("DB Iterator encountered an error: %v", err))
	}
	app.Logger.Info(fmt.Sprintf("Loaded %d balances from Pebble DB: %+v", count, app.State.Ledger))

	iter2, err := app.State.DB.NewIter(&pebble.IterOptions{
		LowerBound: []byte("validator:"),
		UpperBound: []byte("validator~"),
	})
	if err != nil {
		app.Logger.Error(fmt.Sprintf("Failed to create validator records: %v", err))
	}
	defer func(iter2 *pebble.Iterator) {
		if err := iter2.Close(); err != nil {
			app.Logger.Error(fmt.Sprintf("Failed to validator close iterator: %v", err))
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
				continue
			}
			var vu types.ValidatorUpdate
			if err = json.Unmarshal(valBytes, &vu); err != nil {
				app.Logger.Error(fmt.Sprintf("Failed to deserialize validator %s: %v", id, err))
				continue
			}
			pubKeyBytes := vu.PubKeyBytes
			app.State.Validator = append(app.State.Validator, vu)
			pubkey, err := cryptoenc.PubKeyFromTypeAndBytes(vu.PubKeyType, pubKeyBytes)
			if err != nil {
				app.Logger.Error(fmt.Sprintf("Failed to decode validator pubkey: %v", err))
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
			app.Logger.Error(fmt.Sprintf("Failed to persist %s: %v\n", node, err))
		}
	}
	app.Logger.Info("[SAVE] Balances successfully persisted to Blockchain PebbleDB.")

	for _, valUpdate := range app.State.Validator {
		pubKeyBytes := valUpdate.PubKeyBytes
		pubkey, err := cryptoenc.PubKeyFromTypeAndBytes(valUpdate.PubKeyType, pubKeyBytes)
		if err != nil {
			app.Logger.Error(fmt.Sprintf("Failed to fetch pub key: %v", err))
		}
		key := "validator:" + string(pubkey.Address())
		jsonBytes, err := json.Marshal(valUpdate)
		if err != nil {
			app.Logger.Error(fmt.Sprintf("Failed to serialize validator %s: %v", key, err))
			continue
		}
		if err := app.State.DB.Set([]byte(key), jsonBytes, pebble.Sync); err != nil {
			app.Logger.Error(fmt.Sprintf("Failed to persist validator %s: %v", key, err))
		}
	}
	app.Logger.Info("Validators successfully persisted to PebbleDB.")
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
// This must be called whenever a TX transitions out of StatusOnGoing so that
// ProcessExpiredTxs stops visiting it on every subsequent block.
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

	// Upper bound: all bucket keys whose window timestamp <= current window.
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
		// The value stored in the bucket entry is the txHash (written by SaveTx).
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

		// Only expire if we have actually passed the TX end time.
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
