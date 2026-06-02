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
	clusterName := os.Getenv("CLUSTER_NAME")
	if clusterName == "" {
		logger.Error("CLUSTER_NAME environment variable not set")
		os.Exit(1)
	}
	logger.Info("Starting ABCI", "cluster", clusterName)
	db, err := pebble.Open(STATE_DB_PATH, &pebble.Options{})
	if err != nil {
		logger.Error("failed to open State DB", "err", err)
		return
	}
	defer func(db *pebble.DB) {
		err := db.Close()
		if err != nil {
			logger.Error("failed to close State DB", "err", err)
		}
	}(db)

	cluster, err := LoadConfig("config.yaml", clusterName)
	if err != nil {
		logger.Error("failed to load config file", "err", err)
		panic(err)
	}
	logger.Info("Config loaded", "cluster", cluster.Name, "nodes", len(cluster.Nodes))
	app := NewMyApp(db, logger, cluster)
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
