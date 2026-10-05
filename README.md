# 1001 Albums Signal Bot

Posts the daily album from [1001albumsgenerator.com](https://1001albumsgenerator.com) to a Signal group chat.

## Setup

### 1. Start Signal API

```bash
docker compose up -d signal
```

### 2. Register your phone number

```bash
# Request verification code
curl -X POST "http://localhost:8080/v1/register/+YOUR_NUMBER"

# Enter the code you receive
curl -X POST "http://localhost:8080/v1/register/+YOUR_NUMBER/verify/CODE"
```

### 3. Join Signal group

Add the registered phone number to your Signal group (from another device).

### 4. Get group ID

```bash
curl "http://localhost:8080/v1/groups/+YOUR_NUMBER"
```

Find your group in the response and copy the `id` field.

### 5. Configure

```bash
cp .env.example .env
```

Edit `.env`:
- `ALBUMS_PROJECT_NAME`: Your 1001albumsgenerator project name (from the URL)
- `SIGNAL_PHONE_NUMBER`: The registered number (e.g., `+31612345678`)
- `SIGNAL_GROUP_ID`: The group ID from step 4 (e.g., `group.abc123==`)
- `SCHEDULE`: Cron schedule (default: `0 9 * * *` = 9:00 AM daily)

### 6. Test

```bash
docker compose run --rm album-bot
```

### 7. Start scheduler

```bash
docker compose up -d
```

## Manual run

```bash
docker compose run --rm album-bot
```

## When a group send hangs

signal-cli (native, 0.14.x) sometimes hangs on a group send instead of
returning an error: it reuses a sender key whose device list the server no
longer agrees with, and the multi-recipient request never gets a response
(AsamK/signal-cli #2101, #2113). The bot handles this on its own:

1. the send times out (150s);
2. a note-to-self reports the failure to the operator;
3. the group's shared sender key is forgotten in signal-cli's account store,
   so the retry redistributes it per device over the path that does report
   device changes;
4. the send is retried once, and a second note reports the outcome.

For step 3 the bot needs signal-cli's data directory mounted read-write
(`SIGNAL_CLI_DATA_DIR`, default `/signal-cli/data`); `docker-compose.yml`
mounts the `signal-data` volume accordingly.

## Tests

```bash
cd bot && python -m pytest tests
```
