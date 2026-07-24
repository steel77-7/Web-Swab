// Package redispubsub handles subscribing to Redis pub/sub channels
// for crawl log events and routing them to the correct websocket client.
package redispubsub

import (
	"context"
	"log"
	"sync"

	"github.com/redis/go-redis/v9"
)

// MessageHandler is called for each message received on a subscribed channel.
// jobID is extracted from the channel name, data is the raw payload.
type MessageHandler func(jobID string, data []byte)

// LogSubscriber manages per-job Redis pub/sub subscriptions.
type LogSubscriber struct {
	client  *redis.Client
	mu      sync.Mutex
	cancels map[string]context.CancelFunc // jobID -> cancel func for that subscription
	handler MessageHandler
}

// NewLogSubscriber creates a new subscriber connected to the given Redis address.
func NewLogSubscriber(addr string, handler MessageHandler) (*LogSubscriber, error) {
	rdb := redis.NewClient(&redis.Options{
		Addr: addr,
	})

	// Verify the connection
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

// InitJobCount initializes the reference count hash in Redis for a new job if it doesn't exist.
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

// channelName returns the Redis channel for a given job ID.
func channelName(jobID string) string {
	return "crawl:logs:" + jobID
}

// Subscribe starts listening for log messages on the channel for the given job ID.
// It runs in a goroutine and delivers messages via the handler.
// Safe to call multiple times for the same jobID (subsequent calls are no-ops).
func (ls *LogSubscriber) Subscribe(jobID string) {
	ls.mu.Lock()
	if _, exists := ls.cancels[jobID]; exists {
		ls.mu.Unlock()
		return // already subscribed
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

// Unsubscribe stops listening for a job's log channel and cleans up.
func (ls *LogSubscriber) Unsubscribe(jobID string) {
	ls.mu.Lock()
	defer ls.mu.Unlock()

	if cancel, exists := ls.cancels[jobID]; exists {
		cancel()
		delete(ls.cancels, jobID)
	}
}

// Close shuts down all subscriptions and the Redis client.
func (ls *LogSubscriber) Close() {
	ls.mu.Lock()
	defer ls.mu.Unlock()

	for jobID, cancel := range ls.cancels {
		cancel()
		delete(ls.cancels, jobID)
	}
	ls.client.Close()
}
