/**
 * Cloudflare Worker API for Discord Bot Reminders & Eve SSO
 * Uses D1 Database for persistent storage
 */

// Eve Online SSO Configuration
const EVE_SSO_URL = 'https://login.eveonline.com/v2/oauth/authorize';
const EVE_TOKEN_URL = 'https://login.eveonline.com/v2/oauth/token';
const EVE_VERIFY_URL = 'https://esi.evetech.net/verify/';
const EVE_ESI_BASE = 'https://esi.evetech.net/latest';

export default {
  async fetch(request, env) {
    // CORS headers for all responses
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, X-API-Key',
    };

    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    // API Key authentication
    const apiKey = request.headers.get('X-API-Key');
    if (!apiKey || apiKey !== env.API_KEY) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }

    const url = new URL(request.url);
    const path = url.pathname;

    try {
      // Route handling
      if (path === '/reminders' && request.method === 'POST') {
        return await createReminder(request, env, corsHeaders);
      } else if (path === '/reminders/due' && request.method === 'GET') {
        return await getDueReminders(env, corsHeaders);
      } else if (path.startsWith('/reminders/user/') && request.method === 'GET') {
        const userId = path.split('/')[3];
        return await getUserReminders(userId, env, corsHeaders);
      } else if (path.startsWith('/reminders/guild/') && request.method === 'GET') {
        const guildId = path.split('/')[3];
        return await getGuildReminders(guildId, env, corsHeaders);
      } else if (path.startsWith('/reminders/') && request.method === 'DELETE') {
        const reminderId = path.split('/')[2];
        return await deleteReminder(reminderId, env, corsHeaders);
      } else if (path === '/cleanup' && request.method === 'POST') {
        return await cleanupOldReminders(env, corsHeaders);
      } else if (path === '/init' && request.method === 'POST') {
        return await initDatabase(env, corsHeaders);
      } else if (path === '/auth/login' && request.method === 'POST') {
        return await createAuthURL(request, env, corsHeaders);
      } else if (path === '/auth/callback' && request.method === 'GET') {
        return await handleAuthCallback(request, env, corsHeaders);
      } else if (path.startsWith('/auth/user/') && request.method === 'GET') {
        const discordId = path.split('/')[3];
        return await getAuthUser(discordId, env, corsHeaders);
      } else if (path === '/auth/users' && request.method === 'GET') {
        return await getAllAuthUsers(env, corsHeaders);
      } else if (path === '/auth/refresh' && request.method === 'POST') {
        return await refreshAuthTokens(env, corsHeaders);
      } else if (path.startsWith('/auth/') && request.method === 'DELETE') {
        const discordId = path.split('/')[2];
        return await deleteAuthUser(discordId, env, corsHeaders);
      } else {
        return new Response(JSON.stringify({ error: 'Not found' }), {
          status: 404,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
      }
    } catch (error) {
      return new Response(JSON.stringify({ error: error.message }), {
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }
  }
};

// Initialize database schema
async function initDatabase(env, corsHeaders) {
  await env.DB.exec(`
    CREATE TABLE IF NOT EXISTS reminders (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      guild_id INTEGER NOT NULL,
      channel_id INTEGER NOT NULL,
      user_id INTEGER NOT NULL,
      reminder_time TEXT NOT NULL,
      message TEXT NOT NULL,
      created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_reminder_time ON reminders(reminder_time);
    CREATE INDEX IF NOT EXISTS idx_user_id ON reminders(user_id);
    CREATE INDEX IF NOT EXISTS idx_guild_id ON reminders(guild_id);
    
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
    CREATE INDEX IF NOT EXISTS idx_discord_id ON authenticated_users(discord_id);
    CREATE INDEX IF NOT EXISTS idx_eve_character_id ON authenticated_users(eve_character_id);
    CREATE INDEX IF NOT EXISTS idx_token_expires ON authenticated_users(token_expires_at);
  `);

  return new Response(JSON.stringify({ message: 'Database initialized' }), {
    status: 200,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  });
}

// Create a new reminder
async function createReminder(request, env, corsHeaders) {
  const data = await request.json();
  const { guild_id, channel_id, user_id, reminder_time, message } = data;

  if (!guild_id || !channel_id || !user_id || !reminder_time || !message) {
    return new Response(JSON.stringify({ error: 'Missing required fields' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  const created_at = new Date().toISOString();

  const result = await env.DB.prepare(
    'INSERT INTO reminders (guild_id, channel_id, user_id, reminder_time, message, created_at) VALUES (?, ?, ?, ?, ?, ?)'
  ).bind(guild_id, channel_id, user_id, reminder_time, message, created_at).run();

  return new Response(JSON.stringify({ 
    message: 'Reminder created',
    id: result.meta.last_row_id 
  }), {
    status: 201,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  });
}

// Get due reminders
async function getDueReminders(env, corsHeaders) {
  const now = new Date().toISOString();
  
  const { results } = await env.DB.prepare(
    'SELECT * FROM reminders WHERE reminder_time <= ?'
  ).bind(now).all();

  return new Response(JSON.stringify({ reminders: results }), {
    status: 200,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  });
}

// Get reminders for a specific user
async function getUserReminders(userId, env, corsHeaders) {
  const { results } = await env.DB.prepare(
    'SELECT id, reminder_time, message, created_at FROM reminders WHERE user_id = ? ORDER BY reminder_time ASC'
  ).bind(userId).all();

  return new Response(JSON.stringify({ reminders: results }), {
    status: 200,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  });
}

// Get all reminders for a guild
async function getGuildReminders(guildId, env, corsHeaders) {
  const { results } = await env.DB.prepare(
    'SELECT * FROM reminders WHERE guild_id = ? ORDER BY reminder_time ASC'
  ).bind(guildId).all();

  return new Response(JSON.stringify({ reminders: results }), {
    status: 200,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  });
}

// Delete a reminder
async function deleteReminder(reminderId, env, corsHeaders) {
  await env.DB.prepare(
    'DELETE FROM reminders WHERE id = ?'
  ).bind(reminderId).run();

  return new Response(JSON.stringify({ message: 'Reminder deleted' }), {
    status: 200,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  });
}

// Cleanup old reminders (45+ days old)
async function cleanupOldReminders(env, corsHeaders) {
  // Calculate date 45 days ago
  const cutoffDate = new Date();
  cutoffDate.setDate(cutoffDate.getDate() - 45);
  const cutoffISO = cutoffDate.toISOString();

  const result = await env.DB.prepare(
    'DELETE FROM reminders WHERE created_at <= ?'
  ).bind(cutoffISO).run();

  return new Response(JSON.stringify({ 
    message: 'Old reminders cleaned up',
    deleted: result.meta.changes 
  }), {
    status: 200,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  });
}

// ============================================
// EVE ONLINE SSO FUNCTIONS
// ============================================

// Create Eve SSO authorization URL
async function createAuthURL(request, env, corsHeaders) {
  const data = await request.json();
  const { discord_id, discord_username } = data;

  if (!discord_id || !discord_username) {
    return new Response(JSON.stringify({ error: 'Missing discord_id or discord_username' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  // Store state for verification (discord_id encoded)
  const state = btoa(JSON.stringify({ discord_id, discord_username, timestamp: Date.now() }));
  
  const params = new URLSearchParams({
    response_type: 'code',
    redirect_uri: env.EVE_CALLBACK_URL,
    client_id: env.EVE_CLIENT_ID,
    scope: 'publicData',
    state: state
  });

  const authUrl = `${EVE_SSO_URL}?${params.toString()}`;

  return new Response(JSON.stringify({ auth_url: authUrl }), {
    status: 200,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  });
}

// Handle OAuth callback from Eve SSO
async function handleAuthCallback(request, env, corsHeaders) {
  const url = new URL(request.url);
  const code = url.searchParams.get('code');
  const state = url.searchParams.get('state');

  if (!code || !state) {
    return new Response('Authorization failed', { status: 400 });
  }

  try {
    // Decode state to get discord info
    const { discord_id, discord_username } = JSON.parse(atob(state));

    // Exchange code for tokens
    const tokenResponse = await fetch(EVE_TOKEN_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': `Basic ${btoa(`${env.EVE_CLIENT_ID}:${env.EVE_CLIENT_SECRET}`)}`
      },
      body: new URLSearchParams({
        grant_type: 'authorization_code',
        code: code
      })
    });

    const tokens = await tokenResponse.json();
    
    if (!tokens.access_token) {
      throw new Error('Failed to get access token');
    }

    // Verify token and get character info
    const verifyResponse = await fetch(EVE_VERIFY_URL, {
      headers: {
        'Authorization': `Bearer ${tokens.access_token}`
      }
    });

    const characterInfo = await verifyResponse.json();

    // Get character details
    const charResponse = await fetch(`${EVE_ESI_BASE}/characters/${characterInfo.CharacterID}/`, {
      headers: { 'User-Agent': 'Discord Bot' }
    });
    const charData = await charResponse.json();

    // Get corporation info
    const corpResponse = await fetch(`${EVE_ESI_BASE}/corporations/${charData.corporation_id}/`, {
      headers: { 'User-Agent': 'Discord Bot' }
    });
    const corpData = await corpResponse.json();

    // Get alliance info if exists
    let allianceData = null;
    if (corpData.alliance_id) {
      const allianceResponse = await fetch(`${EVE_ESI_BASE}/alliances/${corpData.alliance_id}/`, {
        headers: { 'User-Agent': 'Discord Bot' }
      });
      allianceData = await allianceResponse.json();
    }

    // Calculate token expiration
    const expiresAt = new Date(Date.now() + (tokens.expires_in * 1000)).toISOString();
    const now = new Date().toISOString();

    // Store in database
    await env.DB.prepare(`
      INSERT OR REPLACE INTO authenticated_users (
        discord_id, discord_username, eve_character_id, eve_character_name,
        eve_corporation_id, eve_corporation_name, eve_corporation_ticker,
        eve_alliance_id, eve_alliance_name, eve_alliance_ticker,
        access_token, refresh_token, token_expires_at, last_updated, created_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(
        (SELECT created_at FROM authenticated_users WHERE discord_id = ?), ?
      ))
    `).bind(
      discord_id,
      discord_username,
      characterInfo.CharacterID,
      characterInfo.CharacterName,
      corpData.corporation_id,
      corpData.name,
      corpData.ticker,
      corpData.alliance_id || null,
      allianceData?.name || null,
      allianceData?.ticker || null,
      tokens.access_token,
      tokens.refresh_token,
      expiresAt,
      now,
      discord_id,
      now
    ).run();

    // Return success page with character info
    const html = `
      <!DOCTYPE html>
      <html>
        <head>
          <title>Authentication Successful</title>
          <style>
            body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; text-align: center; }
            .success { color: #28a745; font-size: 24px; margin-bottom: 20px; }
            .info { background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0; }
          </style>
        </head>
        <body>
          <div class="success">✅ Authentication Successful!</div>
          <div class="info">
            <h2>${characterInfo.CharacterName}</h2>
            <p>${allianceData ? `[${allianceData.ticker}] ` : ''}${corpData.ticker}</p>
            <p>Your Discord nickname will be updated shortly.</p>
          </div>
          <p>You can now close this window and return to Discord.</p>
        </body>
      </html>
    `;

    return new Response(html, {
      status: 200,
      headers: { 'Content-Type': 'text/html' }
    });

  } catch (error) {
    return new Response(`Authentication error: ${error.message}`, { status: 500 });
  }
}

// Get authenticated user info
async function getAuthUser(discordId, env, corsHeaders) {
  const { results } = await env.DB.prepare(
    'SELECT * FROM authenticated_users WHERE discord_id = ?'
  ).bind(discordId).all();

  if (results.length === 0) {
    return new Response(JSON.stringify({ authenticated: false }), {
      status: 200,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  return new Response(JSON.stringify({ authenticated: true, user: results[0] }), {
    status: 200,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  });
}

// Get all authenticated users
async function getAllAuthUsers(env, corsHeaders) {
  const { results } = await env.DB.prepare(
    'SELECT discord_id, discord_username, eve_character_name, eve_corporation_ticker, eve_alliance_ticker, token_expires_at, last_updated FROM authenticated_users ORDER BY discord_username'
  ).all();

  return new Response(JSON.stringify({ users: results }), {
    status: 200,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  });
}

// Refresh expired tokens and update character info
async function refreshAuthTokens(env, corsHeaders) {
  const now = new Date().toISOString();
  
  // Get users with expired or soon-to-expire tokens (within 1 hour)
  const oneHourFromNow = new Date(Date.now() + 3600000).toISOString();
  const { results } = await env.DB.prepare(
    'SELECT * FROM authenticated_users WHERE token_expires_at <= ?'
  ).bind(oneHourFromNow).all();

  const refreshed = [];
  const failed = [];

  for (const user of results) {
    try {
      // Refresh token
      const tokenResponse = await fetch(EVE_TOKEN_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'Authorization': `Basic ${btoa(`${env.EVE_CLIENT_ID}:${env.EVE_CLIENT_SECRET}`)}`
        },
        body: new URLSearchParams({
          grant_type: 'refresh_token',
          refresh_token: user.refresh_token
        })
      });

      const tokens = await tokenResponse.json();

      if (!tokens.access_token) {
        throw new Error('Failed to refresh token');
      }

      // Get updated character info
      const charResponse = await fetch(`${EVE_ESI_BASE}/characters/${user.eve_character_id}/`, {
        headers: { 'User-Agent': 'Discord Bot' }
      });
      const charData = await charResponse.json();

      const corpResponse = await fetch(`${EVE_ESI_BASE}/corporations/${charData.corporation_id}/`, {
        headers: { 'User-Agent': 'Discord Bot' }
      });
      const corpData = await corpResponse.json();

      // Get alliance info if exists
      let allianceData = null;
      if (corpData.alliance_id) {
        const allianceResponse = await fetch(`${EVE_ESI_BASE}/alliances/${corpData.alliance_id}/`, {
          headers: { 'User-Agent': 'Discord Bot' }
        });
        allianceData = await allianceResponse.json();
      }

      const expiresAt = new Date(Date.now() + (tokens.expires_in * 1000)).toISOString();

      // Update database
      await env.DB.prepare(`
        UPDATE authenticated_users SET
          eve_corporation_id = ?,
          eve_corporation_name = ?,
          eve_corporation_ticker = ?,
          eve_alliance_id = ?,
          eve_alliance_name = ?,
          eve_alliance_ticker = ?,
          access_token = ?,
          refresh_token = ?,
          token_expires_at = ?,
          last_updated = ?
        WHERE discord_id = ?
      `).bind(
        corpData.corporation_id,
        corpData.name,
        corpData.ticker,
        corpData.alliance_id || null,
        allianceData?.name || null,
        allianceData?.ticker || null,
        tokens.access_token,
        tokens.refresh_token,
        expiresAt,
        now,
        user.discord_id
      ).run();

      refreshed.push({
        discord_id: user.discord_id,
        character_name: user.eve_character_name,
        corporation: corpData.ticker,
        alliance: allianceData?.ticker || null
      });

    } catch (error) {
      failed.push({
        discord_id: user.discord_id,
        error: error.message
      });
    }
  }

  return new Response(JSON.stringify({ refreshed, failed }), {
    status: 200,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  });
}

// Delete authenticated user
async function deleteAuthUser(discordId, env, corsHeaders) {
  await env.DB.prepare(
    'DELETE FROM authenticated_users WHERE discord_id = ?'
  ).bind(discordId).run();

  return new Response(JSON.stringify({ message: 'User authentication deleted' }), {
    status: 200,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  });
}
