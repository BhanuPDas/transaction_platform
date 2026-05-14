package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"sort"
)

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

func GenerateTxHash(decodedStrTx []byte) string {
	hash := sha256.Sum256(decodedStrTx)
	return hex.EncodeToString(hash[:])
}
