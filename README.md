# Web-Swab 🕷️

A distributed web crawler with depth-aware crawling, real-time log streaming, and a terminal UI client.

## Architecture

```
┌──────────┐   WebSocket   ┌──────────┐   HTTP/TCP   ┌──────────┐
│  Client   │ ───────────► │  Server   │ ───────────► │  Broker   │
│  (Go TUI) │ ◄─────────── │   (Go)    │              │          │
└──────────┘   logs/export └──────────┘              └────┬─────┘
                                │                         │
                                │                         │ TCP pull
                                │                         ▼
                           ┌────┴─────┐             ┌──────────┐
                           │ Postgres  │ ◄────────── │ Crawler   │
                           │          │              │ (Python)  │
                           └──────────┘              └────┬─────┘
                                                          │
                                                     ┌────┴─────┐
                                                     │  Redis    │
                                                     │ (cache +  │
                                                     │  pub/sub) │
                                                     └──────────┘
```

| Component | Language | Description |
|-----------|----------|-------------|
| **Server** | Go | WebSocket server that accepts crawl jobs from the client, pushes them to the broker, and streams real-time logs back via Redis pub/sub |
| **Crawler** | Python | Connects to the broker over TCP, crawls pages at the requested depth, extracts links/content, and stores everything in Postgres |
| **Client** | Go | Terminal UI (Bubble Tea) that connects to the server, submits crawl jobs, and displays live logs |

## Prerequisites

- **Go** 1.25+
- **Python** 3.10+
- **PostgreSQL** running locally
- **Redis** running locally
- **golang-migrate** CLI ([install guide](https://github.com/golang-migrate/migrate))

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/steel77-7/Web-Swab.git
cd Web-Swab
```

### 2. Create the database

```bash
createdb crawler
```

### 3. Run migrations

```bash
make migrate-up
```

### 4. Configure environment variables

Each component has its own `.env` file with sensible defaults. Edit them if your setup differs.

**Server** — `server/.env`

```env
DB_URI = postgresql://postgres:postgres@localhost/crawler?sslmode=disable
BROKER_URL = 127.0.0.1
BROKER_PORT = 8000
SERVER_URL = 127.0.0.1:7000
SERVER_PORT = 7000
MAX_HEADER_BYTES = 1048576
REDIS_URL = localhost:6379
```

**Crawler** — `crawler/.env`

```env
BROKER_URL = 127.0.0.1
BROKER_HTTP_PORT = 8000
BROKER_TCP_PORT = 9000
BROKER_SECRET = secret
DB_URI = postgresql://postgres:postgres@localhost/crawler?sslmode=disable
REDIS_URL = localhost
REDIS_PORT = 6379
CRAWLER_USER_AGENT = SteelCrawler/1.0 (+https://github.com/steel77-7/)
```

**Client** — set the `SERVER_URL` env var (defaults to `localhost:7000` if unset):

```bash
export SERVER_URL=localhost:7000
```

### 5. Install Python dependencies

```bash
cd crawler
python -m venv .venv
source .venv/bin/activate   # or .venv/bin/activate.fish
pip install -r requirements.txt
cd ..
```

## Running

All three components need to be running simultaneously. Open three terminals:

### Terminal 1 — Server

```bash
make run-server
```

### Terminal 2 — Crawler

```bash
make run-crawler
```

### Terminal 3 — Client

```bash
make run-client
```

## Make Targets

| Target | Description |
|--------|-------------|
| `make build-server` | Compile the Go server → `bin/server` |
| `make run-server` | Build and run the server |
| `make build-client` | Compile the Go client → `bin/client` |
| `make run-client` | Build and run the TUI client |
| `make run-crawler` | Run the Python crawler |
| `make migrate-up` | Apply all pending database migrations |
| `make migrate-down` | Roll back the last migration |

## Project Structure

```
.
├── server/                  # Go WebSocket server
│   ├── main.go              # Entry point
│   ├── config/              # Config loader (env vars)
│   ├── internals/
│   │   ├── broker/          # Pushes jobs to the broker
│   │   ├── db/              # Postgres pool + repositories
│   │   ├── export/          # Zip export builder
│   │   ├── redis/           # Redis pub/sub log subscriber
│   │   └── types/           # Shared types & config struct
│   ├── websockets/          # WebSocket handler
│   └── .env
│
├── crawler/                 # Python crawling engine
│   ├── main.py              # Entry point
│   ├── conf/                # Config loader (dotenv)
│   ├── broker/              # Sends sub-jobs back to broker
│   ├── caching/             # Redis cache + pub/sub logging
│   ├── crawler/             # Core crawl logic
│   ├── db/                  # SQLAlchemy DB layer
│   ├── jobhandler/          # Job deserialization
│   ├── models/              # SQLModel / Pydantic models
│   ├── socket_client/       # TCP broker client
│   ├── soup/                # BeautifulSoup HTML extractor
│   └── .env
│
├── client/                  # Go TUI client
│   ├── main.go              # Entry point
│   ├── socket/              # WebSocket client
│   └── ui/                  # Bubble Tea TUI
│
├── migrations/              # SQL migration files
└── makefile                 # Build & run targets
```
