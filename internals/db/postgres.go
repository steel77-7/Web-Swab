// here the connection to the db will be made and the pub sub will be made here
package db

import (
	"context"
	"log"
)

// func NewDbPool() (*pgxpool.Pool, func(), error) {
// 	pool, err := pgxpool.Connect(context.Background(), config.Conf.DB_URI)
// 	f := func() {}
// 	if err != nil {
// 		log.Fatal("Couldnt connect to the database: ", err)
// 		return nil, f, err
// 	}
// 	return pool, func() { pool.Close() }, nil

// }
var CTX = context.Background()

func NewDbPool() (*pgxpool.Pool, error) {
	pool, err := pgxpool.Connect(CTX, config.Conf.DB_URI)
	//	f := func() {}
	if err != nil {
		log.Fatal("Couldnt connect to the database: ", err)
		return nil, err
	}
	return pool, nil

}
