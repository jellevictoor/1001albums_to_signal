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
