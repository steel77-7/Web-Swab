package main

import (
	"context"
	"log"

	ws "github.com/steel77-7/Web-Swab/socket"
	"github.com/steel77-7/Web-Swab/ui"
)

func main() {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	client := ws.NewClient(ctx, cancel)
	client.Start()
	log.Println("connected to server, launching UI...")

	// Run the Bubble Tea TUI — this blocks until the user quits.
	// The TUI reads server events from ws.LogChan internally.
	ui.Run()

	log.Println("client shut down")
}
