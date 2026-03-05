package main

import (
	"context"
	"github.com/cockroachdb/pebble/v2"
	"github.com/cometbft/cometbft/abci/server"
	"github.com/cometbft/cometbft/libs/log"
	"os"
	"os/signal"
	"syscall"
	"time"
)

const STATE_DB_PATH = "/root/abci/state.db"

func main() {
	logger := log.NewTMLogger(log.NewSyncWriter(os.Stdout)).With("module", "main")
	logger.Info("--- Starting ABCI with Persistence enabled ---")
	db, err := pebble.Open(STATE_DB_PATH, &pebble.Options{})
	if err != nil {
		logger.Error("failed to open state DB", "err", err)
		return
	}
	defer func(db *pebble.DB) {
		err := db.Close()
		if err != nil {
			logger.Error("failed to close state DB", "err", err)
		}
	}(db)

	app := NewMyApp(db, logger)
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	rpcAddr := "0.0.0.0:7373"
	listen := "0.0.0.0:5555"
	go func() {
		logger.Info("Starting API server", "addr", listen)
		if err := StartHTTPServer(ctx, listen, rpcAddr); err != nil {
			logger.Error("API server failed", "err", err)
		}
		logger.Info("API server stopped")
	}()
	addr := "tcp://127.0.0.1:26658"
	if len(os.Args) > 1 {
		addr = os.Args[1]
	}
	sv := server.NewSocketServer(addr, app)
	logger.Info("ABCI server listening", "addr", addr)
	go func() {
		if err := sv.Start(); err != nil {
			logger.Error("ABCI server error", "err", err)
			stop()
		}
	}()
	<-ctx.Done()
	logger.Info("Shutdown signal received")
	logger.Info("Stopping ABCI server...")
	if err := sv.Stop(); err != nil {
		logger.Error("Error stopping ABCI server", "err", err)
	}
	time.Sleep(200 * time.Millisecond)
	logger.Info("Shutdown complete")
}
