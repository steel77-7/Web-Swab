package db

import (
	"context"
	"log"
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
		jobID := notification.Payload
		//then launch the paylaod to the redis pub sub from where the  the socket hadnler will catch it and then feed to some connection
		// a map keeping track of the thing ...and then msg on the update channel and then that trasnferred to then a map will be used to do it in O(1) time so yesssss
		// but the go routines will scale lineraly to the connections ......500 mb .......too much
	}

}
