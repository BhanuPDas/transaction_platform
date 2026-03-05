package relayer

import (
	"context"
	"github.com/cometbft/cometbft/libs/log"
	rpchttp "github.com/cometbft/cometbft/rpc/client/http"
)

type Relayer struct {
	cfg    Config
	logger log.Logger
}

func NewRelayer(cfg Config, logger log.Logger) *Relayer {
	return &Relayer{
		cfg:    cfg,
		logger: logger,
	}
}

func (r *Relayer) Start(ctx context.Context) error {

	clientA, err := rpchttp.New(r.cfg.ClusterAURL)
	if err != nil {
		return err
	}

	clientB, err := rpchttp.New(r.cfg.ClusterBURL)
	if err != nil {
		return err
	}

	dedup := NewDedupStore()

	forwardAtoB := NewForwarder(
		"ForwarderA",
		clientA,
		clientB,
		r.cfg,
		dedup,
		r.logger,
	)

	forwardBtoA := NewForwarder(
		"ForwarderB",
		clientB,
		clientA,
		r.cfg,
		dedup,
		r.logger,
	)

	if err := forwardAtoB.Start(ctx); err != nil {
		return err
	}

	if err := forwardBtoA.Start(ctx); err != nil {
		return err
	}

	<-ctx.Done()
	return nil
}
