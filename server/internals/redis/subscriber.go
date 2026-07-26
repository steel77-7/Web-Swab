package redispubsub

import (
	"context"
	"log"
	"sync"

	"github.com/redis/go-redis/v9"
)

type MessageHandler func(jobID string, data []byte)

type LogSubscriber struct {
	client  *redis.Client
	mu      sync.Mutex
	cancels map[string]context.CancelFunc
	handler MessageHandler
}

func NewLogSubscriber(addr string, handler MessageHandler) (*LogSubscriber, error) {
	rdb := redis.NewClient(&redis.Options{
		Addr: addr,
	})

	ctx := context.Background()
	if err := rdb.Ping(ctx).Err(); err != nil {
		return nil, err
	}
	log.Printf("redis connected: %s", addr)

	return &LogSubscriber{
		client:  rdb,
		cancels: make(map[string]context.CancelFunc),
		handler: handler,
	}, nil
}

func (ls *LogSubscriber) InitJobCount(jobID string) error {
	ctx := context.Background()
	key := "job:" + jobID
	err := ls.client.HSetNX(ctx, key, "count", 1).Err()
	if err != nil {
		log.Printf("failed to init job count for %s: %v", jobID, err)
		return err
	}
	log.Printf("initialized job count hash for %s with count=1", jobID)
	return nil
}

func channelName(jobID string) string {
	return "crawl:logs:" + jobID
}

func (ls *LogSubscriber) Subscribe(jobID string) {
	ls.mu.Lock()
	if _, exists := ls.cancels[jobID]; exists {
		ls.mu.Unlock()
		return
	}

	ctx, cancel := context.WithCancel(context.Background())
	ls.cancels[jobID] = cancel
	ls.mu.Unlock()

	channel := channelName(jobID)
	pubsub := ls.client.Subscribe(ctx, channel)

	go func() {
		defer pubsub.Close()
		log.Printf("redis subscribed to %s", channel)

		ch := pubsub.Channel()
		for {
			select {
			case msg, ok := <-ch:
				if !ok {
					return
				}
				ls.handler(jobID, []byte(msg.Payload))
			case <-ctx.Done():
				log.Printf("redis unsubscribed from %s", channel)
				return
			}
		}
	}()
}

func (ls *LogSubscriber) Unsubscribe(jobID string) {
	ls.mu.Lock()
	defer ls.mu.Unlock()

	if cancel, exists := ls.cancels[jobID]; exists {
		cancel()
		delete(ls.cancels, jobID)
	}
}

func (ls *LogSubscriber) Close() {
	ls.mu.Lock()
	defer ls.mu.Unlock()

	for jobID, cancel := range ls.cancels {
		cancel()
		delete(ls.cancels, jobID)
	}
	ls.client.Close()
}
