package types

type JobStatus string

const (
	Pending    JobStatus = "pending"
	Processing JobStatus = "processing"
	Done       JobStatus = "done"
	Failed     JobStatus = "failed"
)

type Config struct {
	DB_URI     string
	BROKER_URL string
	CLIENT_URL string
	SERVER_URL string
}

// processing the jobs
type Job struct {
	ID     string    `json:"id"`
	Status JobStatus `json:"status"`
	Url    string    `json:"url"`
	Depth  int       `json:"depth"`
	UserID string    `json:"userid"`
}

// for auth and storing the user
type User struct {
	ID     string `json:"id"`
	APIKey string `json:"api_key"`
}

type JobRepository interface {
	CreateJob(job *Job) error
	UpdateStatus(job *Job) error
}

// requests
type JobRequest struct {
	JobData Job `json:"job"`
}

// tbs
type Metadata struct {
	ID    string `json:"id"`
	Url   string `json:"url"`
	State bool   `json:"state"`
}

type JobTbs struct {
	Data     Job      `json:"job"`
	MetaData Metadata `json:"metadata"`
}

// responses
type APIResponse struct {
	Success bool        `json:"success"`
	Code    int         `json:"code"`
	Data    interface{} `json:"data,omitempty"`
	Error   string      `json:"error,omitempty"`
}
