package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"github.com/hashicorp/serf/client"
	"log"
	"net/http"
	"time"
)

func StartHTTPServer(ctx context.Context, listenAddr string, rpcAddr string) error {
	c, err := client.ClientFromConfig(&client.Config{Addr: rpcAddr})
	if err != nil {
		return fmt.Errorf("failed to create RPC client: %w", err)
	}
	go func() {
		<-ctx.Done()
		_ = c.Close()
	}()

	mux := http.NewServeMux()
	mux.HandleFunc("/members", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			w.WriteHeader(http.StatusMethodNotAllowed)
			return
		}
		members, err := c.Members()
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		writeJSON(w, members)
	})

	mux.HandleFunc("/updatetags", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			w.WriteHeader(http.StatusMethodNotAllowed)
			return
		}
		var req struct {
			Tags       map[string]string `json:"tags"`
			DeleteTags []string          `json:"delete_tags"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, "invalid json: "+err.Error(), http.StatusBadRequest)
			return
		}
		if req.Tags == nil && len(req.DeleteTags) == 0 {
			http.Error(w, "nothing to update", http.StatusBadRequest)
			return
		}
		if err := c.UpdateTags(req.Tags, req.DeleteTags); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	})

	httpSrv := &http.Server{
		Addr:    listenAddr,
		Handler: mux,
	}

	errCh := make(chan error, 1)
	go func() {
		log.Printf("HTTP server listening on %s", listenAddr)
		errCh <- httpSrv.ListenAndServe()
	}()

	select {
	case <-ctx.Done():
		// shutdown server gracefully
		sctx, scancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer scancel()
		_ = httpSrv.Shutdown(sctx)
		return nil
	case err := <-errCh:
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return err
	}
}

func writeJSON(w http.ResponseWriter, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(v)
}
