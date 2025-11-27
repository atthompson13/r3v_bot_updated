-- Initialize reminders table
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    reminder_time TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_reminder_time ON reminders(reminder_time);
CREATE INDEX IF NOT EXISTS idx_user_id ON reminders(user_id);
CREATE INDEX IF NOT EXISTS idx_guild_id ON reminders(guild_id);
