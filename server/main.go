package main

import (
	"fmt"
	"log"
	"net/http"
	"time"

	"github.com/joho/godotenv"
	"github.com/steel77-7/Web-Swab/config"
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
		ReadTimeout:    5 * time.Second,
		WriteTimeout:   5 * time.Second,
		IdleTimeout:    10 * time.Second,
		MaxHeaderBytes: 1 << 20,
	}
	log.Print("Server is running")
	log.Fatal(server.ListenAndServe())

}
