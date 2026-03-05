package main

import (
	"context"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/cometbft/cometbft/libs/log"

	"relayer/internal/relayer"
)

func main() {

	cfg := relayer.Config{
		ClusterAURL:    os.Getenv("CLUSTER_A"),
		ClusterBURL:    os.Getenv("CLUSTER_B"),
		Query:          "tm.event='Tx'",
		BroadcastMode:  "async",
		RequestTimeout: 5 * time.Second,
	}

	logger := log.NewTMLogger(log.NewSyncWriter(os.Stdout))

	r := relayer.NewRelayer(cfg, logger)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	go func() {
		c := make(chan os.Signal, 1)
		signal.Notify(c, syscall.SIGINT, syscall.SIGTERM)
		<-c
		cancel()
	}()

	if err := r.Start(ctx); err != nil {
		logger.Error("relayer stopped", "err", err)
	}
}
