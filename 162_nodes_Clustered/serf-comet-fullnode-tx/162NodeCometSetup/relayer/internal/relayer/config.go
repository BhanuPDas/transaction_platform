package relayer

import "time"

type ClusterConfig struct {
	ID  string `yaml:"id"`
	URL string `yaml:"url"`
}

type Config struct {
	Clusters       []ClusterConfig `yaml:"clusters"`
	Query          string          `yaml:"query"`
	BroadcastMode  string          `yaml:"broadcast_mode"`
	RequestTimeout time.Duration   `yaml:"request_timeout"`
}
