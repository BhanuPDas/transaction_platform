package relayer

import (
	"context"
	"fmt"
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
	if len(r.cfg.Clusters) < 2 {
		return fmt.Errorf("at least 2 clusters required, got %d", len(r.cfg.Clusters))
	}

	// Build all RPC clients upfront, indexed by position
	clients := make([]*rpchttp.HTTP, len(r.cfg.Clusters))
	for i, cl := range r.cfg.Clusters {
		client, err := rpchttp.New(cl.URL)
		if err != nil {
			return fmt.Errorf("failed to create client for cluster %s: %w", cl.ID, err)
		}
		clients[i] = client
	}

	dedup := NewDedupStore()

	// For each cluster: subscribe to it, fan-out to all OTHER clusters
	for i, cl := range r.cfg.Clusters {
		source := clients[i]

		// Build target list = all clusters except source
		targets := make([]*rpchttp.HTTP, 0, len(clients)-1)
		targetIDs := make([]string, 0, len(clients)-1)
		for j, c := range clients {
			if j != i {
				targets = append(targets, c)
				targetIDs = append(targetIDs, r.cfg.Clusters[j].ID)
			}
		}

		forwarder := NewForwarder(
			cl.ID,
			source,
			targets,
			targetIDs,
			r.cfg,
			dedup,
			r.logger,
		)

		if err := forwarder.Start(ctx); err != nil {
			return fmt.Errorf("failed to start forwarder for cluster %s: %w", cl.ID, err)
		}

		r.logger.Info("Forwarder started",
			"source", cl.ID,
			"targets", targetIDs,
		)
	}
	<-ctx.Done()
	return nil
}
