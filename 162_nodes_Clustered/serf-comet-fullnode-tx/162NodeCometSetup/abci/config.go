package main

type ClusterEntry struct {
	Name  string   `yaml:"name"`
	Nodes []string `yaml:"nodes"`
}

type TopologyConfig struct {
	InitialBalance int64          `yaml:"initial_balance"`
	Clusters       []ClusterEntry `yaml:"clusters"`
}

type ResolvedCluster struct {
	Name           string
	InitialBalance int64
	Nodes          []string
}
