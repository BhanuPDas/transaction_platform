package relayer

import (
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"github.com/cometbft/cometbft/libs/log"
	rpchttp "github.com/cometbft/cometbft/rpc/client/http"
	ctypes "github.com/cometbft/cometbft/rpc/core/types"
	"github.com/cometbft/cometbft/types"
	"strings"
	"time"
)

type Forwarder struct {
	name      string
	source    *rpchttp.HTTP
	targets   []*rpchttp.HTTP
	targetIDs []string
	query     string
	mode      string
	dedup     *DedupStore
	logger    log.Logger
	timeout   time.Duration
}

func NewForwarder(
	name string,
	source *rpchttp.HTTP,
	targets []*rpchttp.HTTP,
	targetIDs []string,
	cfg Config,
	dedup *DedupStore,
	logger log.Logger,
) *Forwarder {
	return &Forwarder{
		name:      name,
		source:    source,
		targets:   targets,
		targetIDs: targetIDs,
		query:     cfg.Query,
		mode:      cfg.BroadcastMode,
		dedup:     dedup,
		logger:    logger,
		timeout:   cfg.RequestTimeout,
	}
}

func (f *Forwarder) Start(ctx context.Context) error {
	if err := f.source.Start(); err != nil {
		return err
	}

	sub, err := f.source.Subscribe(ctx, f.name, f.query)
	if err != nil {
		return err
	}

	go f.listen(ctx, sub)
	return nil
}

func (f *Forwarder) listen(ctx context.Context, ch <-chan ctypes.ResultEvent) {
	for {
		select {
		case <-ctx.Done():
			return
		case ev, ok := <-ch:
			if !ok {
				f.logger.Error("subscription channel closed", "source", f.name)
				return
			}
			f.handleEvent(ctx, ev)
		}
	}
}

func (f *Forwarder) handleEvent(ctx context.Context, ev ctypes.ResultEvent) {
	txBytes := ev.Data.(types.EventDataTx).Tx

	// Base64 decode (strip surrounding quotes if present)
	rawTx := string(txBytes)
	if strings.HasPrefix(rawTx, "\"") && strings.HasSuffix(rawTx, "\"") {
		rawTx = rawTx[1 : len(rawTx)-1]
	}
	decodedTx, err := base64.StdEncoding.DecodeString(rawTx)
	if err != nil {
		f.logger.Error("failed to decode base64 tx", "source", f.name, "error", err)
		return
	}

	// Dedup check
	hash := sha256.Sum256(decodedTx)
	hashStr := hex.EncodeToString(hash[:])
	if f.dedup.Seen(hashStr) {
		f.logger.Debug("duplicate tx skipped", "source", f.name, "hash", hashStr)
		return
	}
	f.dedup.Add(hashStr)

	// Fan-out: broadcast to every target cluster
	for i, target := range f.targets {
		targetID := f.targetIDs[i]

		ctxTimeout, cancel := context.WithTimeout(ctx, f.timeout)

		var broadcastErr error
		switch f.mode {
		case "async":
			_, broadcastErr = target.BroadcastTxAsync(ctxTimeout, txBytes)
		case "sync":
			_, broadcastErr = target.BroadcastTxSync(ctxTimeout, txBytes)
		default:
			_, broadcastErr = target.BroadcastTxCommit(ctxTimeout, txBytes)
		}

		cancel()

		if broadcastErr != nil {
			// Log per-target failure but continue to remaining targets
			f.logger.Error("broadcast failed",
				"source", f.name,
				"target", targetID,
				"hash", hashStr,
				"error", broadcastErr,
			)
		} else {
			f.logger.Info("relayed tx",
				"source", f.name,
				"target", targetID,
				"hash", hashStr,
			)
		}
	}
}
