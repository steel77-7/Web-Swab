package api

import (
	"log"

	"github.com/coder/websocket"
	"github.com/gin-gonic/gin"
	"github.com/steel77-7/Web-Swab/internals/broker"
	"github.com/steel77-7/Web-Swab/internals/db"
	response "github.com/steel77-7/Web-Swab/internals/responses"
	"github.com/steel77-7/Web-Swab/internals/types"
	"github.com/steel77-7/Web-Swab/websockets"
)

func Home(c *gin.Context) { //  / route
	c.JSON(200, gin.H{})

}

// make a middleware to authenticate this request
func Ingest(c *gin.Context) { // ingest route
	api_key := c.Request.Header["key"]
	user_id := c.Request.Header["user"]

	//this will then be sent to verify db to store or verify shit
	var data types.JobRequest
	err := c.ShouldBindJSON(&data)
	if err != nil {
		log.Print("Couldnt bind json in the ingest endpoint")
		return
	}
	//verify with the db
	if !db.UserHandler.VerifyUser(types.User{ID: user_id[0], APIKey: api_key[0]}) {
		response.Fail(c, 404, "User not found")
		return
	}

	err_broker := broker.PushToBroker(data.JobData)
	if err_broker != nil {
		log.Print("Couldnt push to the broker:", err_broker)
		response.Fail(c, 500, err_broker.Error())
		return
	}
	//if the job is added to the broker
	response.Success(c, 200, struct{}{})

}

func SocketHandler(c *gin.Context) {
	log.Print("socket handler")

	apiKey := c.GetHeader("Key")
	userID := c.GetHeader("User")

	if !db.UserHandler.VerifyUser(types.User{
		ID:     userID,
		APIKey: apiKey,
	}) {
		c.AbortWithStatus(401)
		return
	}

	conn, err := websocket.Accept(c.Writer, c.Request, &websocket.AcceptOptions{
		InsecureSkipVerify: true,
	})
	if err != nil {
		log.Println("Handshake failed:", err)
		return
	}

	websockets.AcceptChan <- conn

	// do NOT write HTTP response here
}
