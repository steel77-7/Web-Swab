package config

import (
	"log"

	"github.com/caarlos0/env/v11"
	"github.com/steel77-7/Web-Swab/internals/types"
)

func LoadConfig() *types.Config {
	log.Print("IT it woirking ???")
	var cfg types.Config
	if err := env.Parse(&cfg); err != nil {
		log.Fatal(err)
	}
	log.Print("cfg")
	log.Print("cfg", cfg.BROKER_URL)

	return &cfg
}

var Conf *types.Config
