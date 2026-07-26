package db

import (
	"context"
	"log"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/steel77-7/Web-Swab/internals/types"
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
	//	job.UserID,
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
	//	&job.UserID,
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
		if err != nil {
			log.Println("job_updates listen error:", err)
			return
		}
		log.Println("job update notification:", notification.Payload)

		ServerSendChan <- notification.Payload
	}
}

// fetcher
// SendToServer is a legacy helper method.
// func (j *JobRepository) SendToServer() { ... }
