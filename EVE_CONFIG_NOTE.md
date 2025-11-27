# IMPORTANT: Eve SSO Configuration

The Eve Online SSO credentials need to be set in **TWO** places to keep everything in sync:

## 1. Bot's .env file
```env
EVE_CLIENT_ID=your_client_id
EVE_CLIENT_SECRET=your_client_secret
EVE_CALLBACK_URL=https://your-domain.com/auth/callback
```

## 2. Worker's wrangler.toml file
```toml
[vars]
EVE_CLIENT_ID = "your_client_id"
EVE_CLIENT_SECRET = "your_client_secret"
EVE_CALLBACK_URL = "https://your-domain.com/auth/callback"
```

**Why both?**
- The **bot's .env** keeps your config for the Discord bot
- The **Worker's wrangler.toml** provides the config to the Cloudflare Worker

**When you change Eve SSO settings:**
1. Update bot's `.env` file
2. Update `worker/wrangler.toml` file
3. Redeploy Worker: `cd worker; wrangler deploy`

**For open-source distribution:**
- Keep your actual credentials in these files (gitignored)
- Users copy `.env.example` and `wrangler.toml`, then fill in their own values
- No need to run `wrangler secret put` commands - everything is in config files!

