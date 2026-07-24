package main

import (
	"fmt"
	"log"
	"net/http"

	"github.com/joho/godotenv"
	"github.com/steel77-7/Web-Swab/config"
	redispubsub "github.com/steel77-7/Web-Swab/internals/redis"
	"github.com/steel77-7/Web-Swab/websockets"
)

// will have a start function
func main() {
	godotenv.Load()

	config.Conf = config.LoadConfig()
	//	router := api.NewRouter()
	//	db.NewDbPoolInit()
	//go db.JobHandler.Listen()
	handler := websockets.NewServer()

	// Set up Redis log subscriber — routes crawler logs to the correct client.
	redisSub, err := redispubsub.NewLogSubscriber(config.Conf.REDIS_URL, func(jobID string, data []byte) {
		handler.SendToSubscriber(jobID, data)
	})
	if err != nil {
		log.Printf("redis subscriber unavailable: %v (log streaming disabled)", err)
	} else {
		handler.SetRedisSubscriber(redisSub)
		defer redisSub.Close()
	}

	//::testing
	// job := types.Job{
	// 	ID:     "test2",
	// 	Status: types.JobStatus("pending"),
	// 	Url:    "https://books.toscrape.com/catalogue/maybe-something-beautiful-how-art-transformed-a-neighborhood_386/index.html",
	// 	Depth:  2,
	// }
	// broker.PushToBroker(job)
	//::testing
	//router.Use(gin.Recovery())
	server := &http.Server{
		Addr:           ":" + fmt.Sprint(7000),
		Handler:        handler,
		MaxHeaderBytes: 1 << 20,
	}
	log.Print("server running on :7000")
	log.Fatal(server.ListenAndServe())
}

