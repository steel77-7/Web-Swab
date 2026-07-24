//here a queue will be made to send the jobs to the broker

package broker

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"time"

	"github.com/steel77-7/Web-Swab/config"
	"github.com/steel77-7/Web-Swab/internals/types"
)

func PushToBroker(job types.Job) error {
	client := &http.Client{
		Timeout: 5 * time.Second,
	}

	tbs, _ := json.Marshal([]types.JobTbs{
		types.JobTbs{
			Data: job,
			MetaData: types.Metadata{
				ID:    job.ID,
				Url:   config.Conf.SERVER_URL,
				State: false,
			},
		},
	},
	)
	log.Printf("pushing job %s to broker", job.ID)
	req, _ := http.NewRequest("POST", "http://"+config.Conf.BROKER_URL+":"+config.Conf.BROKER_PORT+"/ingest", bytes.NewBuffer(tbs))
	resp, err := client.Do(req)
	if err != nil {
		log.Printf("broker request failed: %v", err)
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode > 300 {
		log.Printf("broker returned status %d", resp.StatusCode)
		return fmt.Errorf("broker returned status %d", resp.StatusCode)
	}
	//just reply with something or some retry logic ............
	return nil
}
