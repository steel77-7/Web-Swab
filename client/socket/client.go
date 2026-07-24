package ws

import (
	"context"
	"log"

	"github.com/coder/websocket"
	"github.com/coder/websocket/wsjson"
)

// LogChan carries the raw payloads read off the server connection, for
// whoever wants to consume/log them.
var LogChan = make(chan []byte, 1000)

// SendChan carries the raw payload bytes the caller wants shipped to the
// server. The client wraps each one in the server's Message envelope
// before writing it, so don't put a pre-wrapped Message on this channel.
var SendChan = make(chan []byte)

// message mirrors the server's Message struct. It has to match exactly —
// same field names/tags — since the server's msgParser just does a plain
// json.Unmarshal into that type.
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
	c, _, err := websocket.Dial(ctx, "ws://localhost:7000/subscribe", nil)
	if err != nil {
		log.Fatal("couldn't connect to the server: ", err)
	}
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
			// wsjson.Write marshals msg to JSON and sends it as a text
			// frame, which is exactly what the server's msgParser expects.
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
	// non-blocking: sendLoop may already have exited on its own (e.g. a
	// write failure), in which case nothing is left to receive here, and
	// a plain `c.quitch <- struct{}{}` would leak this goroutine forever.
	select {
	case c.quitch <- struct{}{}:
	default:
	}
	c.cancel()
}

// shutdown closes the connection and cancels the client's context so
// anything watching ctx.Done() knows the client is going away. Safe to
// call from either loop even if the other already triggered it.
func (c *Client) shutdown() {
	c.ws.Close(websocket.StatusNormalClosure, "client disconnecting")
	c.cancel()
}
