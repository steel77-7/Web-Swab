package api

import (
	"log"
	"scraper/internals/broker"
	response "scraper/internals/responses"
	"scraper/internals/types"
	"scraper/internals/websockets"

	"github.com/coder/websocket"
	"github.com/gin-gonic/gin"
)

func Home(c *gin.Context) { //  / route
	c.JSON(200, gin.H{})

}

// make a middleware to authenticate this request
func Ingest(c *gin.Context) { // ingest route
	api_key := c.Request.Header["key"]
	//this will then be sent to verify db to store or verify shit
	var data types.JobRequest
	err := c.ShouldBindJSON(&data)
	if err != nil {
		log.Print("Couldnt bind json in the ingest endpoint")
		return
	}
	//verify with the db
	//verify_key(apikey)

	err_broker := broker.PushToBroker(data.JobData)
	if err_broker != nil {
		log.Print("Couldnt push to the broker:", err_broker)
		response.Fail(c, 500, err_broker.Error())
		return
	}
	//if the job is added to the broker
	response.Success(c, 200, struct{}{})

}

func Poll(c *gin.Context) {
	c.JSON(200, gin.H{})
}

func SocketHanlder(c *gin.Context) {
	conn, err := websocket.Accept(c.Writer, c.Request, &websocket.AcceptOptions{
		InsecureSkipVerify: true,
	})
	if err != nil {
		log.Fatal("Handshake failed: ", err)
		return
	}
	//	v:=c.Request.Context()
	websockets.AcceptChan <- conn

}
