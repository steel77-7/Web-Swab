package config

import (
	"go/types"
	"log"

	"github.com/caarlos0/env/v11"
)

func LoadConfig() *types.Config {
	var cfg types.Config
	//var redisCfg RedisConfig

	if err := env.Parse(&cfg); err != nil {
		log.Fatal(err)
	}

	// if err := env.Parse(&redisCfg); err != nil {
	// 	log.Fatal(err)
	// }

	return &cfg
}

var Conf *types.Config
