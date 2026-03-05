package relayer

import "time"

type Config struct {
	ClusterAURL    string
	ClusterBURL    string
	Query          string
	BroadcastMode  string
	RequestTimeout time.Duration
}
