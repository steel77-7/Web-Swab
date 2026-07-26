#local env here for dev
DB_URL := postgresql://postgres:postgres@localhost/crawler?sslmode=disable

.PHONY: build-server run-server build-client run-client run-crawler migrate-up migrate-down

# ── Server (Go) ──────────────────────────────────────────────
build-server:
	cd server && go build -o ../bin/server .

run-server: build-server
	cd server && ../bin/server

# ── Client (Go) ──────────────────────────────────────────────
build-client:
	cd client && go build -o ../bin/client .

run-client: build-client
	cd client && ../bin/client

# ── Crawler (Python) ─────────────────────────────────────────
run-crawler:
	cd crawler && python main.py

# ── Migrations ───────────────────────────────────────────────
migrate-up:
	migrate -path migrations -database $(DB_URL) up

migrate-down:
	migrate -path migrations -database $(DB_URL) down 1
