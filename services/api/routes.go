package api

import (
	"github.com/gin-gonic/gin"
)

func NewRouter() *gin.Engine {
	router := gin.New()
	router.Use(gin.Recovery())

	router.GET("/", Home)
	router.POST("/ingest", Ingest)
	router.POST("/poll", Poll)
	router.GET("/ws")

	return router
}
