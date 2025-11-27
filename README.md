# R3V Discord Bot

A comprehensive Discord bot for managing recruitment threads, reminders, and Eve Online SSO authentication with persistent storage using Cloudflare D1.

## Features

### Thread Management
- **`/recruit`** - Create a new recruitment thread with applicant (Recruiter role required)
- **`/officer`** - Elevate a recruitment thread to officer discussion (Director role required)
- **`/close`** - Archive a thread and remove all non-staff users (Recruiter role required)
- **`/remove`** - Remove a user from the current thread (Recruiter or Director role required)
- **`/threads`** - List all active recruitment and officer threads
- **`/reopen`** - Reopen an archived thread

### Reminders
- **`/remind`** - Set a reminder in the current thread (minutes, hours, or days)
- **`/list-reminders`** - View all your active reminders
- **`/cancel-reminder`** - Cancel a specific reminder by ID

### Eve Online Integration
- **`/auth`** - Get SSO link to authenticate with Eve Online
- **`/status`** - View authenticated characters and their corporation/alliance info
- Automatic nickname updates based on Eve character data (every 10 minutes)
- List of unauthenticated users for compliance tracking

## Architecture

### Bot (Python)
- **Framework**: discord.py with app_commands
- **HTTP Client**: aiohttp for Worker API communication
- **Logging**: File-based rotating logs (5MB max, 5 backups) + Discord channel logging
- **Background Tasks**: 
  - Reminder checking (every 1 minute)
  - Old reminder cleanup (daily, 45+ days)
  - Nickname updates (every 10 minutes)

### Worker API (Cloudflare Workers)
- **Runtime**: Node.js on Cloudflare Workers
- **Database**: Cloudflare D1 (SQLite-compatible)
- **Endpoints**:
  - `/reminders` - CRUD operations for reminders
  - `/auth/*` - Eve Online SSO authentication flow
  - `/cleanup` - Database maintenance

### Database Schema

#### Reminders Table
```sql
reminders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  guild_id TEXT NOT NULL,
  channel_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  reminder_time INTEGER NOT NULL,
  message TEXT,
  created_at INTEGER DEFAULT (unixepoch())
)
```

#### Authentication Table
```sql
authenticated_users (
  discord_id TEXT PRIMARY KEY,
  character_id TEXT NOT NULL,
  character_name TEXT NOT NULL,
  corporation_ticker TEXT,
  alliance_ticker TEXT,
  access_token TEXT NOT NULL,
  refresh_token TEXT NOT NULL,
  expires_at INTEGER NOT NULL,
  created_at INTEGER DEFAULT (unixepoch()),
  updated_at INTEGER DEFAULT (unixepoch())
)
```

## Setup

### Prerequisites
- Python 3.8+
- Node.js 18+
- Cloudflare account
- Discord Bot Token
- Eve Online Application (for SSO)

### 1. Bot Configuration

Create `.env` file in the root directory:

```env
DISCORD_TOKEN=your_bot_token_here
GUILD_ID=your_guild_id_here
RECRUITER_ROLE_ID=your_recruiter_role_id_here
DIRECTOR_ROLE_ID=your_director_role_id_here
WORKER_API_URL=https://discord-bot-api.YOUR-SUBDOMAIN.workers.dev
WORKER_API_KEY=your_secure_api_key_here
LOG_CHANNEL_ID=your_log_channel_id_here
```

### 2. Worker Configuration

Navigate to `worker/` directory and configure `wrangler.toml`:

```toml
name = "discord-bot-api"
main = "src/index.js"
compatibility_date = "2024-01-01"

[[d1_databases]]
binding = "DB"
database_name = "r3v"
database_id = "your-database-id-here"

[vars]
API_KEY = "your_secure_api_key_here"
EVE_CLIENT_ID = "your_eve_client_id"
EVE_CLIENT_SECRET = "your_eve_client_secret"
EVE_CALLBACK_URL = "https://your-domain.com/auth/callback"
```

### 3. Database Setup

Create D1 database:
```bash
cd worker
wrangler d1 create r3v
```

Deploy schemas:
```bash
wrangler d1 execute r3v --remote --file=./schema.sql
wrangler d1 execute r3v --remote --file=./schema-auth.sql
```

### 4. Deploy Worker

```bash
cd worker
wrangler deploy
```

### 5. Install Bot Dependencies

```bash
pip install discord.py python-dotenv aiohttp
```

### 6. Run the Bot

```bash
python "import discord.py"
```

## Eve Online SSO Setup

1. Create an application at https://developers.eveonline.com/
2. Set the callback URL to match your custom domain (e.g., `https://your-domain.com/auth/callback`)
3. Request the `publicData` scope
4. Add credentials to `worker/wrangler.toml`
5. Update `EVE_CALLBACK_URL` in wrangler.toml with your actual domain

**Security Note**: Using a custom domain for the callback URL is strongly recommended instead of the default `workers.dev` subdomain.

See `EVE_SSO_SETUP.md` for detailed setup instructions.

## Discord Bot Permissions

The bot requires the following permissions:
- Read Messages/View Channels
- Send Messages
- Create Public Threads
- Send Messages in Threads
- Manage Threads
- Manage Messages (for removing users from threads)
- Manage Nicknames (for Eve character sync)
- Read Message History

Bot Intents Required:
- `GUILDS`
- `GUILD_MEMBERS`
- `MESSAGE_CONTENT`

## Logging

Logs are stored in two locations:
1. **File**: `logs/bot.log` (rotating, max 5MB, 5 backups)
2. **Discord**: Channel specified by `LOG_CHANNEL_ID`

Log levels:
- `INFO` 📝 - General operations
- `WARNING` ⚠️ - Non-critical issues
- `ERROR` ❌ - Critical failures

## Maintenance

### Automatic Cleanup
- Reminders older than 45 days are automatically deleted daily
- Failed reminders are logged but not retried

### Manual Database Operations

List reminders:
```bash
wrangler d1 execute r3v --remote --command="SELECT * FROM reminders"
```

List authenticated users:
```bash
wrangler d1 execute r3v --remote --command="SELECT discord_id, character_name, corporation_ticker, alliance_ticker FROM authenticated_users"
```

## Troubleshooting

### Bot won't start
- Verify all environment variables in `.env` are set correctly
- Check that role IDs and channel IDs are valid
- Ensure Discord token has not expired

### Reminders not working
- Verify Worker API is accessible
- Check API key matches between `.env` and `wrangler.toml`
- Review Worker logs: `wrangler tail`

### Eve SSO authentication failing
- Ensure callback URL matches exactly in both Eve app and wrangler.toml
- Verify client ID and secret are correct
- Check that the callback URL is publicly accessible

### Nickname updates not working
- Verify bot has "Manage Nicknames" permission
- Ensure bot's role is higher than the target user's highest role
- Check that Eve SSO authentication is working

## File Structure

```
R3V bot/
├── import discord.py        # Main bot application
├── .env                     # Bot configuration (not in git)
├── .env.example            # Configuration template
├── README.md               # This file
├── EVE_SSO_SETUP.md        # Eve SSO setup guide
├── suggestions.txt         # Feature suggestions
├── logs/                   # Log files directory
│   └── bot.log
└── worker/                 # Cloudflare Worker
    ├── src/
    │   └── index.js        # Worker API endpoints
    ├── wrangler.toml       # Worker configuration
    ├── schema.sql          # Reminders table schema
    └── schema-auth.sql     # Authentication table schema
```

## Support

For issues or questions:
1. Check logs in `logs/bot.log` and Discord bot-logs channel
2. Review Worker logs with `wrangler tail`
3. Verify all configuration files are correct
4. Ensure all dependencies are installed

## License

This bot is for private use within the R3V Discord server.
