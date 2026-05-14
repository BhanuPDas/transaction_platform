package main

import (
	"context"
	"github.com/cometbft/cometbft/libs/log"
	"os"
	"os/signal"
	"syscall"

	"relayer/internal/relayer"
)

func main() {

	cfg, err := relayer.LoadConfig("config.yaml")
	if err != nil {
		panic(err)
	}
	logger := log.NewTMLogger(log.NewSyncWriter(os.Stdout))

	r := relayer.NewRelayer(*cfg, logger)

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
