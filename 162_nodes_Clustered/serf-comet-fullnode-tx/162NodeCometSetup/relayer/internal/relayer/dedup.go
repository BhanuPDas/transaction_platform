package relayer

import (
	"sync"
)

type DedupStore struct {
	mtx  sync.RWMutex
	seen map[string]struct{}
}

func NewDedupStore() *DedupStore {
	return &DedupStore{
		seen: make(map[string]struct{}),
	}
}

func (d *DedupStore) Seen(hash string) bool {
	d.mtx.RLock()
	defer d.mtx.RUnlock()
	_, ok := d.seen[hash]
	return ok
}

func (d *DedupStore) Add(hash string) {
	d.mtx.Lock()
	defer d.mtx.Unlock()
	d.seen[hash] = struct{}{}
}
