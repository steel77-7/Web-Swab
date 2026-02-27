//here a queue will be made to send the jobs to the broker

package broker

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	config "scraper"
	"scraper/internals/types"
	"time"
)

func PushToBroker(job types.Job) error {
	client := &http.Client{
		Timeout: 10 * time.Millisecond,
	}
	//data, _ := json.Marshal(job)
	//then configure how the structure of the data tbs has to be
	// something like{
	//metadata
	// then data
	//
	//}
	// meta data will have id or something ...maybe
	tbs, _ := json.Marshal(types.JobTbs{
		Data: job,
		MetaData: types.Metadata{
			ID:    job.ID,
			Url:   config.Conf.SERVER_URL,
			State: false,
		},
	})
	req, _ := http.NewRequest("POST", config.Conf.BROKER_URL+"/ingest", bytes.NewBuffer(tbs))
	resp, err := client.Do(req)
	if err != nil {
		log.Print("Couldnt send the request to the broker")
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode > 300 {
		log.Print("Response code: ", resp.StatusCode)
		return fmt.Errorf("Couldnt send the repsonse ...status code:", resp.StatusCode)
	}
	//just reply with something or some retry logic ............
	return nil
}
