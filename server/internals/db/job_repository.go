package db

import (
	"context"
	"log"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/steel77-7/Web-Swab/internals/types"
	"github.com/steel77-7/Web-Swab/websockets"
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
		job.Url,
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

func (j *JobRepository) FetchJob(id string) error {
	q := `
	SELECT id, status, url, depth, user_id
	FROM jobs
	WHERE id = $1
	`
	var job types.Job
	row := j.Pool.QueryRow(CTX, q, id)
	err := row.Scan(
		&job.ID,
		&job.Status,
		&job.Url,
		&job.Depth,
		&job.UserID,
	)
	if err != nil {
		log.Println("job fetch error:", err)
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

var ServerSendChan = make(chan string, 1000)

// func (j *JobRepository) Listen() {
// 	_, err := j.Pool.Exec(CTX, "LISTEN FOR job_updates")
// 	if err != nil {
// 		log.Fatal("COuldnt start the listening to the db")
// 		return
// 	}
// 	for {

// 		notification, err := j.Pool.WaitForNotification(CTX)
// 		if err != nil {
// 			log.Println("Listening error:", err)
// 			continue
// 		}
// 		ServerSendChan <- notification.Payload

// 	}

// }

func (j *JobRepository) Listen() {
	conn, err := j.Pool.Acquire(CTX)
	if err != nil {
		log.Fatal("Could not acquire connection for listening:", err)
	}
	defer conn.Release()
	_, err = conn.Exec(CTX, "LISTEN job_updates")
	if err != nil {
		log.Fatal("Could not start the listening to the db:", err)
	}

	log.Println("Started listening for job_updates...")

	for {

		notification, err := conn.Conn().WaitForNotification(CTX)
		log.Print("new job updated")
		if err != nil {
			log.Println("Listening error:", err)
			return
		}

		ServerSendChan <- notification.Payload
	}
}

// fetcher
func (j *JobRepository) SendToServer() {
	q := `SELECT id ,user_id, status FROM jobs WHERE id = $1`
	for {
		id := <-ServerSendChan
		row := j.Pool.QueryRow(CTX, q, id)
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
