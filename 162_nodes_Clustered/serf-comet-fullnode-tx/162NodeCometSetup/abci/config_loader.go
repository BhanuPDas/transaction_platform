package main

import (
	"fmt"
	"gopkg.in/yaml.v3"
	"os"
	"strings"
)

func LoadConfig(path string, clusterName string) (*ResolvedCluster, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("reading config %q: %w", path, err)
	}

	var cfg TopologyConfig
	if err := yaml.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("parsing config: %w", err)
	}
	if cfg.InitialBalance <= 0 {
		return nil, fmt.Errorf("config: initial_balance must be > 0")
	}

	for _, c := range cfg.Clusters {
		if c.Name != clusterName {
			continue
		}
		if len(c.Nodes) == 0 {
			return nil, fmt.Errorf("cluster %q has empty nodes list", clusterName)
		}
		return &ResolvedCluster{
			Name:           clusterName,
			InitialBalance: cfg.InitialBalance,
			Nodes:          c.Nodes,
		}, nil
	}

	return nil, fmt.Errorf("cluster %q not found in config (available: %s)",
		clusterName, availableClusterNames(cfg.Clusters))
}

func availableClusterNames(clusters []ClusterEntry) string {
	names := make([]string, len(clusters))
	for i, c := range clusters {
		names[i] = c.Name
	}
	return strings.Join(names, ", ")
}
