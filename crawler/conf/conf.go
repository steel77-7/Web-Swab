package conf

import (
	"log"

	"github.com/caarlos0/env/v11"
)

type Config struct {
	BrokerUrl  string `env : "BROKER_URL" envDefault: "127.0.0.1"`
	BrokerPort int    `env : "BROKER_PORT" envDefault: "9000"`
}

func LoadConfig() *Config {
	var cfg Config

	if err := env.Parse(&cfg); err != nil {
		log.Fatal(err)
	}

	return &cfg
}
