# Eve Online SSO Setup Guide

## Step 1: Register Eve Application

1. Go to https://developers.eveonline.com/
2. Log in with your Eve Online account
3. Click "Create New Application"
4. Fill in the details:
   - **Application Name**: R3V Discord Bot
   - **Description**: Discord bot for Rev3nants Wrath
   - **Connection Type**: Authentication & API Access
   - **Permissions**: Check "publicData" only
   - **Callback URL**: `https://discord-bot-api.austintthompson1.workers.dev/auth/callback`
5. Click "Create Application"
6. Copy your **Client ID** and **Secret Key**

## Step 2: Configure Worker with Eve Credentials

Edit `worker/wrangler.toml` and update the Eve SSO configuration:

```toml
[vars]
EVE_CLIENT_ID = "your_client_id_here"
EVE_CLIENT_SECRET = "your_secret_key_here"
EVE_CALLBACK_URL = "https://your-domain.com/auth/callback"
```

Also update your bot's `.env` file with the same values for documentation/reference.

## Step 3: Initialize Database with Auth Tables

```powershell
wrangler d1 execute r3v --remote --file=./schema-auth.sql
```

Or run the init endpoint (already includes auth tables):
```powershell
curl -X POST https://discord-bot-api.austintthompson1.workers.dev/init -H "X-API-Key: YOUR_API_KEY"
```

## Step 4: Deploy Worker

```powershell
cd "E:\R3V bot\worker"
wrangler deploy
```

## Step 5: Test the System

1. In Discord, type `/auth`
2. Click the link in your DM
3. Authorize with Eve Online
4. Your nickname should update within a few minutes

## How It Works

1. User runs `/auth` command
2. Bot generates unique SSO link via Worker API
3. User clicks link → redirected to Eve Online login
4. User authorizes → Eve redirects back to Worker
5. Worker exchanges code for tokens
6. Worker fetches character/corp/alliance info from ESI
7. Worker stores everything in D1 database
8. Bot updates nickname every 6 hours: `[ALLIANCE] CORP | CharacterName`
9. Bot refreshes tokens before they expire
10. If refresh fails, user gets DM to re-authenticate

## Director Commands

- `/status` - See who is authenticated, who needs reauth, and who hasn't authenticated

## Automatic Features

- Nicknames update every 6 hours
- Tokens refresh automatically before expiring
- Users get DM if token refresh fails
- Corp/alliance changes sync automatically
