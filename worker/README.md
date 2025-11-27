# Cloudflare Worker Setup

## Prerequisites
- Cloudflare account
- Wrangler CLI installed: `npm install -g wrangler`
- Logged in: `wrangler login`

## Setup Steps

### 1. Install Dependencies
```bash
cd worker
npm install
```

### 2. Set API Key Secret
Generate a secure API key and set it:
```bash
wrangler secret put API_KEY
# When prompted, enter a strong random key (you'll use this in the bot's .env)
```

### 3. Initialize Database
Run the schema migration:
```bash
npm run init-db
```

Or manually:
```bash
wrangler d1 execute r3v --remote --file=./schema.sql
```

### 4. Deploy Worker
```bash
npm run deploy
```

This will give you a URL like: `https://discord-bot-api.YOUR-SUBDOMAIN.workers.dev`

### 5. Update Bot Configuration
Add to your bot's `.env` file:
```
WORKER_API_URL=https://discord-bot-api.YOUR-SUBDOMAIN.workers.dev
WORKER_API_KEY=your-api-key-from-step-2
```

## API Endpoints

- `POST /init` - Initialize database (first-time setup)
- `POST /reminders` - Create a reminder
- `GET /reminders/due` - Get due reminders
- `GET /reminders/user/{user_id}` - Get user's reminders
- `GET /reminders/guild/{guild_id}` - Get all guild reminders
- `DELETE /reminders/{reminder_id}` - Delete a reminder

All requests require `X-API-Key` header.

## Testing Locally
```bash
npm run dev
```

Worker will be available at `http://localhost:8787`

## Database Management
View database contents:
```bash
wrangler d1 execute discord-bot-db --remote --command="SELECT * FROM reminders"
```
