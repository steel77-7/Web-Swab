package main

import (
	"fmt"
	"log"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/joho/godotenv"
	"github.com/steel77-7/Web-Swab/config"
	"github.com/steel77-7/Web-Swab/internals/db"
	"github.com/steel77-7/Web-Swab/services/api"
	"github.com/steel77-7/Web-Swab/websockets"
)

// will have a start function
func main() {
	log.Print("1")
	godotenv.Load()

	config.Conf = config.LoadConfig()
	router := api.NewRouter()
	db.NewDbPoolInit()
	go db.JobHandler.Listen()
	go func() {
		server, err := websockets.NewServer()
		if err != nil {
			log.Fatal("COuldnt start the websocket server")
			return
		}
		go server.AcceptConnections()
		go server.Writer()
	}()
	router.Use(gin.Recovery())
	server := &http.Server{
		Addr:           ":" + fmt.Sprint(9000),
		Handler:        router,
		ReadTimeout:    5 * time.Second,
		WriteTimeout:   5 * time.Second,
		IdleTimeout:    10 * time.Second,
		MaxHeaderBytes: 1 << 20,
	}
	log.Print("Server is running")
	log.Fatal(server.ListenAndServe())

}
