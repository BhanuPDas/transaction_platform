package relayer

import "time"

type Config struct {
	ClusterAURL    string        `yaml:"cluster_a_url"`
	ClusterBURL    string        `yaml:"cluster_b_url"`
	Query          string        `yaml:"query"`
	BroadcastMode  string        `yaml:"broadcast_mode"`
	RequestTimeout time.Duration `yaml:"request_timeout"`
}
