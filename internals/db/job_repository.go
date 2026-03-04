package db

import (
	"context"
	"log"
	"scraper/internals/types"
	"scraper/internals/websockets"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

type JobRepository struct {
	Pool *pgxpool.Pool
}

func (j *JobRepository) StoreJob(job types.Job) error {
	q := `INSERT INTO jobs (id, url, depth, status, created_at, updated_at, user_id) VALUES ($1, $2, $3, $4, $5, $6, $7)`

	_, err := j.Pool.Exec(
		context.Background(),
		q,
		job.ID,
		job.URL,
		job.Depth,
		job.Status,
		time.Now(),
		time.Now(),
		job.UserID,
	)

	if err != nil {
		return err
	}

	return nil

}

func (j *JobRepository) UpdateStatus(id string, status string) error {
	q := `UPDATE jobs SET status  = $1 WHERE id = $2 NOTIFY job_updates , $2`
	_, err := j.Pool.Exec(CTX, q, status, id)
	if err != nil {
		return err
	}
	return nil
}

// func (j *JobRepository) Listen() {
// 	_, err := j.Pool.Exec(CTX, "LISTEN FOR job_updates")
// 	if err != nil {
// 		log.Fatal("COuldnt start the listening to the db")
// 		return
// 	}
// 	for {
// 		func(){

// 		notification, err := j.Pool.WaitForNotification(CTX)
// 		if err != nil {
// 			log.Println("Listening error:", err)
// 			continue
// 		}
// 		}
// 		//thsi may casue a lot of delay but lets do it for now
// 		// maybe have another goroutine for picking up the eevtns and then send them to the socket server
// 		jobID := notification.Payload

// 		websockets.DBEventChan<-
// 	}

// }
var ServerSendChan = make(chan string, 1000)

func (j *JobRepository) Listen() {
	_, err := j.Pool.Exec(CTX, "LISTEN FOR job_updates")
	if err != nil {
		log.Fatal("COuldnt start the listening to the db")
		return
	}
	for {

		notification, err := j.Pool.WaitForNotification(CTX)
		if err != nil {
			log.Println("Listening error:", err)
			continue
		}
		ServerSendChan <- notification.Payload

		//thsi may casue a lot of delay but lets do it for now
		// maybe have another goroutine for picking up the eevtns and then send them to the socket server

		//	websockets.DBEventChan<-
	}

}

// fetcher
func (j *JobRepository) SendToServer() {
	q := `SELECT id ,user_id, status FROM jobs WHERE id = $1`
	for {
		id := <-ServerSendChan
		row := j.Pool.QueryRow(CTX, q, id)
		// if err != nil {
		// 	log.Print("Error in the send to server thing in the job repo")
		// 	continue
		// }
		var jobID string
		var userID string
		var status string

		err := row.Scan(&jobID, &userID, &status)
		if err != nil {
			log.Print("Error in the send to server thing in the job repo")
			continue
		}
		websockets.DBEventChan <- websockets.Event{
			ClientID: userID, Status: types.JobStatus(status), JobID: jobID,
		}
	}
}
