-- Add authenticated users table
CREATE TABLE IF NOT EXISTS authenticated_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id TEXT NOT NULL UNIQUE,
    discord_username TEXT NOT NULL,
    eve_character_id INTEGER NOT NULL,
    eve_character_name TEXT NOT NULL,
    eve_corporation_id INTEGER NOT NULL,
    eve_corporation_name TEXT NOT NULL,
    eve_corporation_ticker TEXT NOT NULL,
    eve_alliance_id INTEGER,
    eve_alliance_name TEXT,
    eve_alliance_ticker TEXT,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    token_expires_at TEXT NOT NULL,
    last_updated TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_discord_id ON authenticated_users(discord_id);
CREATE INDEX IF NOT EXISTS idx_eve_character_id ON authenticated_users(eve_character_id);
CREATE INDEX IF NOT EXISTS idx_token_expires ON authenticated_users(token_expires_at);
