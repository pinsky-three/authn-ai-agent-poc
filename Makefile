.PHONY: up down logs reset help

up:    ## start all services
	docker compose up --build -d

down:  ## stop all services
	docker compose down -v

logs:  ## tail logs
	docker compose logs -f --tail=200

reset: ## reset and rebuild
	docker compose down -v && docker compose up --build

help:  ## show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
