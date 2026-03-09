package websockets

import (
	"context"
	"encoding/json"
	"log"
	"sync"
	"time"

	"github.com/coder/websocket"
	"github.com/google/uuid"
	"github.com/steel77-7/Web-Swab/internals/broker"
	"github.com/steel77-7/Web-Swab/internals/types"
)

type Message struct {
	Kind string
	Data []byte
}

type Event struct {
	Status   types.JobStatus
	ClientID string
	JobID    string
}

var AcceptChan = make(chan *websocket.Conn, 1000)
var DBEventChan = make(chan Event)

type Client struct {
	ID   string
	Conn *websocket.Conn
	Req  *context.Context
	// Mu   *sync.Mutex
}
type Server struct {
	Clients map[string]*Client
	Mu      *sync.Mutex
	// Ctx     *context.Context
}

func NewServer() (*Server, error) {
	//	ctx, cancel := context.WithTimeout(context.Background(), time.Second*10)

	return &Server{
		Clients: make(map[string]*Client),
		Mu:      &sync.Mutex{},
		//Ctx:     &ctx,
	}, nil
}

func (s *Server) AcceptConnections() {
	ctx, _ := context.WithTimeout(context.Background(), time.Second*10)
	for {
		newclient := <-AcceptChan
		log.Print("new socket client")
		//this will then be registered to the Server
		id := uuid.New().String()
		c := &Client{ID: id, Conn: newclient}
		s.Clients[id] = c
		go s.readloop(c, ctx)

	}
}

func (s *Server) readloop(c *Client, ctx context.Context) {
	defer c.Conn.Close(websocket.StatusNormalClosure, "")

	for {
		_, data, err := c.Conn.Read(ctx)
		if err != nil {
			log.Printf("Couldnt read values from client %v: %v", c.ID, err)
			return
		}

		var msg Message
		if err := json.Unmarshal(data, &msg); err != nil {
			log.Printf("Failed to unmarshal: %v", err)
			continue
		}
		s.messagehandler(c, msg)
	}
}

func (s *Server) messagehandler(c *Client, msg Message) {
	switch msg.Kind {
	case "NEW":
		{
			//agr merer pass new messages hai to unka me ikya krunga??
			// send them to the broker
			// parse the message now
			var job types.Job
			err := json.Unmarshal(msg.Data, &job)
			if err != nil {
				log.Print("Couldnt unmarshal  the data:", err)
				return
			}
			broker.PushToBroker(job)
		}
	case "CLOSE":
		{
			c.Conn.Close(websocket.StatusNormalClosure, "")
			log.Print("Connection to the socket closed: ", c.ID)
			//dletign the user from the client map
			delete(s.Clients, c.ID)
		}
	case "":
		{

		}
	}
}

func (s *Server) send(c *Client, msg Message) error {
	tbs, _ := json.Marshal(msg)
	err := c.Conn.Write(*c.Req, websocket.MessageText, []byte(tbs))
	if err != nil {
		log.Print("COuldnt write to socket :", c.ID)
		return err
	}
	return nil
}

// short lived go routines for seindiong data back to the client
func (s *Server) Writer() {
	for {
		event := <-DBEventChan
		//then feed thsi to the map
		val, ok := s.Clients[event.ClientID]
		if !ok {
			log.Print("Client removed from the server: ", event.ClientID)
			continue
		}
		tbs, _ := json.Marshal(event)
		s.send(val, Message{
			Kind: "Status",
			Data: []byte(tbs),
		})

	}
}
