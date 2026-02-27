package api

import (
	"log"
	"scraper/internals/broker"
	"scraper/internals/types"

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

	broker.PushToBroker(data.JobData)
	c.JSON(200, gin.H{})

}

func Poll(c *gin.Context) {
	c.JSON(200, gin.H{})
}
