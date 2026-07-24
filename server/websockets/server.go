// this file will be used in the final version
// rn raw http calls will be used to enter data into the server
package websockets

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"log"
	"net"
	"net/http"
	"sync"
	"time"

	"github.com/coder/websocket"
	"github.com/google/uuid"
	"github.com/steel77-7/Web-Swab/internals/broker"
	redispubsub "github.com/steel77-7/Web-Swab/internals/redis"
	"github.com/steel77-7/Web-Swab/internals/types"
	"golang.org/x/time/rate"
)

type Message struct {
	Kind string `json:"kind"`
	Data []byte `json:"data"`
}

type subscriber struct {
	msgs      chan Message
	closeSlow func()
}

type Server struct {
	subscriberMessageBuffer int
	publishLimiter          *rate.Limiter
	logf                    func(f string, v ...any)
	ServeMux                http.ServeMux
	subscribersMu           sync.Mutex
	subscribers             map[string]*subscriber
	redisSub                *redispubsub.LogSubscriber
}

func NewServer() *Server {
	s := &Server{
		subscriberMessageBuffer: 16,
		logf:                    log.Printf,
		subscribers:             make(map[string]*subscriber),
		publishLimiter:          rate.NewLimiter(rate.Every(time.Millisecond*100), 8),
	}
	//	s.serveMux.Handle("/", http.FileServer(http.Dir(".")))
	s.ServeMux.HandleFunc("/subscribe", s.subscribeHandler)
	log.Print("websocket server initialized")
	return s
}

// SetRedisSubscriber attaches the Redis log subscriber to the server.
func (s *Server) SetRedisSubscriber(rs *redispubsub.LogSubscriber) {
	s.redisSub = rs
}

func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	s.ServeMux.ServeHTTP(w, r)
}

func (s *Server) subscribe(w http.ResponseWriter, r *http.Request) error {
	var mu sync.Mutex
	log.Print("new subscriber connecting")
	var c *websocket.Conn
	var closed bool
	sub := &subscriber{
		msgs: make(chan Message, s.subscriberMessageBuffer),
		closeSlow: func() {
			mu.Lock()
			defer mu.Unlock()
			closed = true
			if c != nil {
				c.Close(websocket.StatusPolicyViolation, "connection too slow")
			}
		},
	}
	id := s.addSubscriber(sub)
	defer s.deleteSubscriber(id)

	// clients are accepted here
	c2, err := websocket.Accept(w, r, nil)
	if err != nil {
		return err
	}
	mu.Lock()
	if closed {
		mu.Unlock()
		return net.ErrClosed
	}
	c = c2
	mu.Unlock()
	defer c.CloseNow()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// jobIDChan receives the job ID when the client sends a DATA message,
	// so we can re-key the subscriber map and start the Redis subscription.
	jobIDChan := make(chan string, 1)

	readErrc := make(chan error, 1)
	go s.readLoop(ctx, c, readErrc, jobIDChan)

	// Track the job ID so we can clean up the Redis subscription on exit.
	var activeJobID string
	defer func() {
		if activeJobID != "" && s.redisSub != nil {
			s.redisSub.Unsubscribe(activeJobID)
			log.Printf("cleaned up redis subscription for job %s", activeJobID)
		}
	}()

	for {
		select {
		case msg := <-sub.msgs:
			err := writeTimeout(ctx, time.Second*5, c, msg.Data)
			if err != nil {
				return err
			}
		case jobID := <-jobIDChan:
			// Re-key subscriber: remove the temp UUID, store under job ID.
			s.rekeySubscriber(id, jobID, sub)
			id = jobID
			activeJobID = jobID

			// Start Redis subscription for this job's logs.
			if s.redisSub != nil {
				s.redisSub.Subscribe(jobID)
				log.Printf("started redis log subscription for job %s", jobID)
			}
		case err := <-readErrc:
			return err
		case <-ctx.Done():
			return ctx.Err()
		}
	}
}

func (s *Server) readLoop(ctx context.Context, c *websocket.Conn, errc chan<- error, jobIDChan chan<- string) {
	for {
		_, data, err := c.Read(ctx)
		if err != nil {
			errc <- err
			return
		}

		parsedMsg, err := msgParser(data)
		if err != nil {
			s.logf("invalid message from client: %v", err)
			continue
		}

		switch parsedMsg.Kind {
		case "DATA":
			var job types.Job
			if err := json.Unmarshal(parsedMsg.Data, &job); err != nil {
				s.logf("invalid job data from client: %v", err)
				continue
			}
			s.logf("job received: %s", string(parsedMsg.Data))

			// Notify the subscribe loop to re-key and start Redis sub.
			if job.ID != "" {
				if s.redisSub != nil {
					s.redisSub.InitJobCount(job.ID)
				}
				select {
				case jobIDChan <- job.ID:
				default:
					// Already sent a job ID, skip re-keying.
				}
			}

			// push to broker
			go func(j types.Job) {
				if err := broker.PushToBroker(j); err != nil {
					s.logf("push to broker failed for job %s: %v", j.ID, err)
				}
			}(job)
		}
	}
}

func (s *Server) subscribeHandler(w http.ResponseWriter, r *http.Request) {
	err := s.subscribe(w, r)
	if errors.Is(err, context.Canceled) || errors.Is(err, io.EOF) || errors.Is(err, net.ErrClosed) {
		return
	}
	status := websocket.CloseStatus(err)
	if status == websocket.StatusNormalClosure ||
		status == websocket.StatusGoingAway ||
		status == websocket.StatusAbnormalClosure {
		return
	}
	if err != nil {
		s.logf("%v", err)
		return
	}
}

func msgParser(msg []byte) (Message, error) {
	var res Message
	err := json.Unmarshal(msg, &res)
	if err != nil {
		return Message{}, err
	}
	return res, nil
}

// publish broadcasts a message to all connected subscribers.
func (s *Server) publish(msg Message) {

	s.publishLimiter.Wait(context.Background())

	s.subscribersMu.Lock()
	defer s.subscribersMu.Unlock()
	for _, sub := range s.subscribers {
		select {
		case sub.msgs <- msg:
		default:
			go sub.closeSlow()
		}
	}
}

// SendToSubscriber sends a log message to a specific subscriber identified by job ID.
func (s *Server) SendToSubscriber(jobID string, data []byte) {
	msg := Message{Kind: "LOG", Data: data}

	s.subscribersMu.Lock()
	defer s.subscribersMu.Unlock()

	sub, ok := s.subscribers[jobID]
	if !ok {
		return
	}

	select {
	case sub.msgs <- msg:
	default:
		go sub.closeSlow()
	}
}

func (s *Server) addSubscriber(sub *subscriber) string {
	id := uuid.NewString()
	s.subscribersMu.Lock()
	s.subscribers[id] = sub
	s.subscribersMu.Unlock()
	return id
}

// rekeySubscriber moves a subscriber from an old key (temp UUID) to a new key (job ID).
func (s *Server) rekeySubscriber(oldID, newID string, sub *subscriber) {
	s.subscribersMu.Lock()
	defer s.subscribersMu.Unlock()
	delete(s.subscribers, oldID)
	s.subscribers[newID] = sub
	log.Printf("subscriber re-keyed: %s -> %s", oldID[:8], newID)
}

func (s *Server) deleteSubscriber(id string) {
	s.subscribersMu.Lock()
	delete(s.subscribers, id)
	s.subscribersMu.Unlock()
}

func writeTimeout(ctx context.Context, timeout time.Duration, c *websocket.Conn, msg []byte) error {
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	return c.Write(ctx, websocket.MessageText, msg)
}
