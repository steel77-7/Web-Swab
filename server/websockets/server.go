//this file will be used in the final version
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

	"github.com/google/uuid"

	"github.com/coder/websocket"
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
	// subscribers             map[*subscriber]struct{}
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
	s.ServeMux.HandleFunc("/publish", s.publishHandler)
	log.Print("its alive")
	return s
}
func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	s.ServeMux.ServeHTTP(w, r)
}
func (s *Server) subscribe(w http.ResponseWriter, r *http.Request) error {
	var mu sync.Mutex
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
	//clients aree accepted here
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
	ctx := c.CloseRead(context.Background())
	for {
		select {
		case msg := <-sub.msgs:
			err := writeTimeout(ctx, time.Second*5, c, msg.Data)
			if err != nil {
				return err
			}
		case <-ctx.Done():
			return ctx.Err()
		}
	}
}

func (s *Server) subscribeHandler(w http.ResponseWriter, r *http.Request) {
	err := s.subscribe(w, r)
	if errors.Is(err, context.Canceled) {
		return
	}
	if websocket.CloseStatus(err) == websocket.StatusNormalClosure ||
		websocket.CloseStatus(err) == websocket.StatusGoingAway {
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
func (s *Server) publishHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != "POST" {
		http.Error(w, http.StatusText(http.StatusMethodNotAllowed), http.StatusMethodNotAllowed)
		return
	}
	body := http.MaxBytesReader(w, r.Body, 8192)
	msg, err := io.ReadAll(body)
	if err != nil {
		http.Error(w, http.StatusText(http.StatusRequestEntityTooLarge), http.StatusRequestEntityTooLarge)
		return
	}
	parsedMsg, _ := msgParser(msg)
	switch parsedMsg.Kind {
	case "DATA":
		{
			// got the  the new request for url
			var data types.Job
			json.Unmarshal(parsedMsg.Data, &data)
			log.Print("data receicevf :", string(parsedMsg.Data))
			//push to broker
		}

	}
	// s.publish(msg)

	w.WriteHeader(http.StatusAccepted)
}
func (s *Server) publish(msg Message) {
	s.subscribersMu.Lock()
	defer s.subscribersMu.Unlock()

	s.publishLimiter.Wait(context.Background())

	for _, sub := range s.subscribers {
		select {
		case sub.msgs <- msg:
		default:
			go sub.closeSlow()
		}
	}
}

func (s *Server) addSubscriber(sub *subscriber) string {
	id := uuid.NewString()
	s.subscribersMu.Lock()
	s.subscribers[id] = sub
	s.subscribersMu.Unlock()
	return id
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
