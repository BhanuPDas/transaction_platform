package relayer

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"time"

	"github.com/cometbft/cometbft/libs/log"
	rpchttp "github.com/cometbft/cometbft/rpc/client/http"
	ctypes "github.com/cometbft/cometbft/rpc/core/types"
	"github.com/cometbft/cometbft/types"
)

type Forwarder struct {
	name    string
	source  *rpchttp.HTTP
	target  *rpchttp.HTTP
	query   string
	mode    string
	dedup   *DedupStore
	logger  log.Logger
	timeout time.Duration
}

func NewForwarder(
	name string,
	source *rpchttp.HTTP,
	target *rpchttp.HTTP,
	cfg Config,
	dedup *DedupStore,
	logger log.Logger,
) *Forwarder {
	return &Forwarder{
		name:    name,
		source:  source,
		target:  target,
		query:   cfg.Query,
		mode:    cfg.BroadcastMode,
		dedup:   dedup,
		logger:  logger,
		timeout: cfg.RequestTimeout,
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
		case ev := <-ch:
			f.handleEvent(ctx, ev)
		}
	}
}

func (f *Forwarder) handleEvent(ctx context.Context, ev ctypes.ResultEvent) {
	txBytes := ev.Data.(types.EventDataTx).Tx

	hash := sha256.Sum256(txBytes)
	hashStr := hex.EncodeToString(hash[:])

	if f.dedup.Seen(hashStr) {
		return
	}

	f.dedup.Add(hashStr)

	ctxTimeout, cancel := context.WithTimeout(ctx, f.timeout)
	defer cancel()

	switch f.mode {
	case "async":
		_, err := f.target.BroadcastTxAsync(ctxTimeout, txBytes)
		if err != nil {
			f.logger.Error("broadcast tx error", "error", err)
		}
	case "sync":
		_, err := f.target.BroadcastTxSync(ctxTimeout, txBytes)
		if err != nil {
			f.logger.Error("broadcast tx error", "error", err)
		}
	default:
		_, err := f.target.BroadcastTxCommit(ctxTimeout, txBytes)
		if err != nil {
			f.logger.Error("broadcast tx error", "error", err)
		}
	}

	f.logger.Info("Relayed tx",
		"direction", f.name,
		"hash", hashStr,
	)
}
