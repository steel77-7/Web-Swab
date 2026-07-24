package config

import (
	"log"

	"github.com/caarlos0/env/v11"
	"github.com/steel77-7/Web-Swab/internals/types"
)

func LoadConfig() *types.Config {
	var cfg types.Config
	if err := env.Parse(&cfg); err != nil {
		log.Fatal("failed to parse config: ", err)
	}
	return &cfg
}

var Conf *types.Config
