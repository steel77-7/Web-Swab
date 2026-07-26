package main

import (
	"log"
	"net/http"

	"github.com/joho/godotenv"
	"github.com/steel77-7/Web-Swab/config"
	"github.com/steel77-7/Web-Swab/internals/db"
	"github.com/steel77-7/Web-Swab/internals/export"
	redispubsub "github.com/steel77-7/Web-Swab/internals/redis"
	"github.com/steel77-7/Web-Swab/websockets"
)

// will have a start function
func main() {
	godotenv.Load()

	config.Conf = config.LoadConfig()
	//	router := api.NewRouter()
	db.NewDbPoolInit()
	//go db.JobHandler.Listen()
	handler := websockets.NewServer()
	if db.JobHandler.Pool != nil {
		handler.SetExporter(export.NewExporter(db.JobHandler.Pool))
	}

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
		Addr:           ":" + config.Conf.SERVER_PORT,
		Handler:        handler,
		MaxHeaderBytes: config.Conf.MAX_HEADER_BYTES,
	}
	log.Printf("server running on :%s", config.Conf.SERVER_PORT)
	log.Fatal(server.ListenAndServe())
}

