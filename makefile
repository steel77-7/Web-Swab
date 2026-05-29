#local env here for dev
DB_URL := postgresql://postgres:postgres@localhost/crawler?sslmode=disable
crawler:
	echo "The crawler make file"

build:
	go build -o bin/main server/cmd/api/main.go

run:
	./bin/main

venv:
	source crawler/.venv/bin/activate/fish

run-crawler:
	python crawler/test_crawler/main.py
migrate-up:
	migrate -path migrations -database $(DB_URL) up
migrate-down:
	migrate -path migrations -database $(DB_URL) down 1
