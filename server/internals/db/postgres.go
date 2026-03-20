// here the connection to the db will be made and the pub sub will be made here
package db

import (
	"context"
	"log"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/steel77-7/Web-Swab/config"
)

var CTX = context.Background()
var JobHandler JobRepository
var UserHandler UserRepository

func NewDbPoolInit() {
	log.Print("2")

	log.Print(config.Conf.DB_URI)
	pool, err := pgxpool.New(CTX, config.Conf.DB_URI)
	//	f := func() {}
	if err != nil {
		log.Fatal("Couldnt connect to the database: ", err)
		return
	}
	JobHandler.Pool = pool
	UserHandler.Pool = pool

}
