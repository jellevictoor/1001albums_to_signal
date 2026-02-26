#!/bin/sh
docker compose build --no-cache album-bot
docker compose run --rm album-bot python main.py --dry-run --force-milestone
