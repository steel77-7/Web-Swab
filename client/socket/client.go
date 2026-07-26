package ws

import (
	"context"
	"log"
	"os"

	"github.com/coder/websocket"
	"github.com/coder/websocket/wsjson"
)

var LogChan = make(chan []byte, 1000)
var SendChan = make(chan []byte)

type message struct {
	Kind string `json:"kind"`
	Data []byte `json:"data"`
}

type Client struct {
	ws     *websocket.Conn
	quitch chan struct{}
	ctx    context.Context
	cancel context.CancelFunc
}

func NewClient(ctx context.Context, cancel context.CancelFunc) *Client {
	serverURL := os.Getenv("SERVER_URL")
	if serverURL == "" {
		serverURL = "localhost:7000"
	}
	wsURL := "ws://" + serverURL + "/subscribe"
	c, _, err := websocket.Dial(ctx, wsURL, nil)
	if err != nil {
		log.Fatal("couldn't connect to the server: ", err)
	}
	c.SetReadLimit(10 * 1024 * 1024)
	log.Println("websocket connected to server")
	return &Client{
		ws:     c,
		quitch: make(chan struct{}),
		ctx:    ctx,
		cancel: cancel,
	}
}

func (c *Client) Start() {
	go c.sendLoop()
	go c.listener()
	log.Println("websocket send/receive loops started")
}

func (c *Client) sendLoop() {
	for {
		select {
		case payload := <-SendChan:
			msg := message{Kind: "DATA", Data: payload}
			if err := wsjson.Write(c.ctx, c.ws, msg); err != nil {
				log.Println("failed to send:", err)
				c.shutdown()
				return
			}
		case <-c.quitch:
			c.shutdown()
			return
		}
	}
}

func (c *Client) listener() {
	for {
		_, data, err := c.ws.Read(c.ctx)
		if err != nil {
			log.Println("read error:", err)
			break
		}
		LogChan <- data
	}
	select {
	case c.quitch <- struct{}{}:
	default:
	}
	c.cancel()
}

func (c *Client) shutdown() {
	c.ws.Close(websocket.StatusNormalClosure, "client disconnecting")
	c.cancel()
}
