package api

import (
	"fmt"
	"log"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
)

// will have a start function
func main() {
	router := gin.New()
	router.Use(gin.Recovery())
	//	router.Get("/")
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
