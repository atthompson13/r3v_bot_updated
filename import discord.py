import discord
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv
import os
import asyncio
from datetime import datetime, timedelta
import logging
from logging.handlers import RotatingFileHandler
import aiohttp

# ----------------------------
# Load .env variables
# ----------------------------
load_dotenv()

# Validate environment variables
required_vars = {
    "DISCORD_TOKEN": os.getenv("DISCORD_TOKEN"),
    "GUILD_ID": os.getenv("GUILD_ID"),
    "RECRUITER_ROLE_ID": os.getenv("RECRUITER_ROLE_ID"),
    "DIRECTOR_ROLE_ID": os.getenv("DIRECTOR_ROLE_ID"),
    "WORKER_API_URL": os.getenv("WORKER_API_URL"),
    "WORKER_API_KEY": os.getenv("WORKER_API_KEY"),
    "BOT_LOGS_CHANNEL_ID": os.getenv("BOT_LOGS_CHANNEL_ID")
}

missing_vars = [var for var, value in required_vars.items() if not value]
if missing_vars:
    print(f"❌ ERROR: Missing required environment variables: {', '.join(missing_vars)}")
    print("Please check your .env file and ensure all required variables are set.")
    exit(1)

try:
    TOKEN = required_vars["DISCORD_TOKEN"]
    GUILD_ID = int(required_vars["GUILD_ID"])
    RECRUITER_ROLE_ID = int(required_vars["RECRUITER_ROLE_ID"])
    DIRECTOR_ROLE_ID = int(required_vars["DIRECTOR_ROLE_ID"])
    WORKER_API_URL = required_vars["WORKER_API_URL"].rstrip('/')
    WORKER_API_KEY = required_vars["WORKER_API_KEY"]
    BOT_LOGS_CHANNEL_ID = int(required_vars["BOT_LOGS_CHANNEL_ID"])
except ValueError as e:
    print(f"❌ ERROR: Invalid environment variable format. GUILD_ID, RECRUITER_ROLE_ID, and DIRECTOR_ROLE_ID must be numbers.")
    exit(1)

# ----------------------------
# File Logging Setup
# ----------------------------
log_formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# Create logs directory if it doesn't exist
if not os.path.exists('logs'):
    os.makedirs('logs')

# Rotating file handler (max 5MB per file, keep 5 backup files)
file_handler = RotatingFileHandler('logs/bot.log', maxBytes=5*1024*1024, backupCount=5)
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.INFO)

# Setup logger
logger = logging.getLogger('DiscordBot')
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# ----------------------------
# Intents
# ----------------------------
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# ----------------------------
# Bot setup
# ----------------------------
bot = commands.Bot(command_prefix="!", intents=intents)

# ----------------------------
# Worker API Helper Functions
# ----------------------------
async def api_request(method: str, endpoint: str, data: dict = None):
    """Make HTTP request to Worker API"""
    headers = {
        'X-API-Key': WORKER_API_KEY,
        'Content-Type': 'application/json'
    }
    
    url = f"{WORKER_API_URL}{endpoint}"
    
    async with aiohttp.ClientSession() as session:
        try:
            if method == 'GET':
                async with session.get(url, headers=headers) as response:
                    return await response.json()
            elif method == 'POST':
                async with session.post(url, headers=headers, json=data) as response:
                    return await response.json()
            elif method == 'DELETE':
                async with session.delete(url, headers=headers) as response:
                    return await response.json()
        except Exception as e:
            logger.error(f"API request failed: {e}")
            return None

async def add_reminder(guild_id: int, channel_id: int, user_id: int, reminder_time: datetime, message: str):
    """Add a reminder via Worker API"""
    data = {
        'guild_id': guild_id,
        'channel_id': channel_id,
        'user_id': user_id,
        'reminder_time': reminder_time.isoformat(),
        'message': message
    }
    return await api_request('POST', '/reminders', data)

async def get_due_reminders():
    """Get all reminders that are due"""
    result = await api_request('GET', '/reminders/due')
    return result['reminders'] if result else []

async def delete_reminder(reminder_id: int):
    """Delete a reminder"""
    return await api_request('DELETE', f'/reminders/{reminder_id}')

async def get_user_reminders(user_id: int):
    """Get all reminders for a specific user"""
    result = await api_request('GET', f'/reminders/user/{user_id}')
    return result['reminders'] if result else []

async def get_all_reminders(guild_id: int):
    """Get all reminders for a guild"""
    result = await api_request('GET', f'/reminders/guild/{guild_id}')
    return result['reminders'] if result else []

# ----------------------------
# Eve SSO API Functions
# ----------------------------
async def create_auth_url(discord_id: str, discord_username: str):
    """Create Eve SSO authorization URL"""
    data = {
        'discord_id': str(discord_id),
        'discord_username': discord_username
    }
    result = await api_request('POST', '/auth/login', data)
    return result['auth_url'] if result else None

async def get_auth_user(discord_id: str):
    """Get authenticated user info"""
    result = await api_request('GET', f'/auth/user/{discord_id}')
    return result if result else None

async def get_all_auth_users():
    """Get all authenticated users"""
    result = await api_request('GET', '/auth/users')
    return result['users'] if result else []

async def refresh_auth_tokens():
    """Refresh expired auth tokens"""
    result = await api_request('POST', '/auth/refresh')
    return result if result else None

async def delete_auth_user(discord_id: str):
    """Delete authenticated user"""
    return await api_request('DELETE', f'/auth/{discord_id}')

# ----------------------------
# Utility: Logging
# ----------------------------
async def log_action(guild: discord.Guild, message: str, level: str = "INFO"):
    """Log actions with timestamp and level to bot-logs channel"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    emoji = {"INFO": "📝", "WARNING": "⚠️", "ERROR": "❌"}.get(level, "📝")
    
    # File and console logging
    log_level = getattr(logging, level, logging.INFO)
    logger.log(log_level, message)
    
    # Channel logging
    log_channel = bot.get_channel(BOT_LOGS_CHANNEL_ID)
    if log_channel:
        try:
            await log_channel.send(f"{emoji} `[{timestamp}]` {message}")
        except Exception as e:
            logger.error(f"Failed to send log to channel: {e}")

# ----------------------------
# Bot Ready
# ----------------------------
@bot.event
async def on_ready():
    logger.info(f"✅ Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        logger.info(f"Synced {len(synced)} commands to guild {GUILD_ID}.")
    except Exception as e:
        logger.error(f"❌ Sync error: {e}")
    
    # Start reminder checker
    check_reminders.start()
    
    # Start cleanup task
    cleanup_old_reminders.start()
    
    # Start nickname updater
    update_nicknames.start()

# ----------------------------
# Reminder Checker Task
# ----------------------------
@tasks.loop(seconds=60)  # Check every minute
async def check_reminders():
    """Background task to check for due reminders"""
    try:
        due_reminders = await get_due_reminders()
        for reminder in due_reminders:
            reminder_id = reminder['id']
            guild_id = reminder['guild_id']
            channel_id = reminder['channel_id']
            user_id = reminder['user_id']
            message = reminder['message']
            
            try:
                guild = bot.get_guild(guild_id)
                if guild:
                    channel = guild.get_channel(channel_id) or guild.get_thread(channel_id)
                    user = guild.get_member(user_id)
                    
                    if channel and user:
                        await channel.send(f"🔔 {user.mention} Reminder: {message}")
                        await log_action(guild, f"Reminder delivered to {user.name}: {message}", "INFO")
                    else:
                        # Fallback to DM if channel is unavailable
                        user_obj = await bot.fetch_user(user_id)
                        if user_obj:
                            try:
                                await user_obj.send(f"🔔 Reminder: {message}")
                            except:
                                pass  # User has DMs disabled
                
                # Delete the reminder after sending
                await delete_reminder(reminder_id)
            except Exception as e:
                logger.error(f"Error sending reminder {reminder_id}: {e}")
                await delete_reminder(reminder_id)  # Delete failed reminders to avoid retry loops
    except Exception as e:
        logger.error(f"Error in check_reminders task: {e}")

@check_reminders.before_loop
async def before_check_reminders():
    """Wait until bot is ready before starting reminder checker"""
    await bot.wait_until_ready()

# ----------------------------
# Cleanup Old Reminders Task
# ----------------------------
@tasks.loop(hours=24)  # Run once per day
async def cleanup_old_reminders():
    """Background task to cleanup reminders older than 45 days"""
    try:
        result = await api_request('POST', '/cleanup')
        if result:
            deleted_count = result.get('deleted', 0)
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old reminders (45+ days)")
    except Exception as e:
        logger.error(f"Error in cleanup_old_reminders task: {e}")

@cleanup_old_reminders.before_loop
async def before_cleanup_old_reminders():
    """Wait until bot is ready before starting cleanup task"""
    await bot.wait_until_ready()

# ----------------------------
# Update Nicknames Task
# ----------------------------
@tasks.loop(hours=6)  # Run every 6 hours
async def update_nicknames():
    """Background task to update Discord nicknames from Eve data"""
    try:
        # Refresh tokens and get updated data
        result = await refresh_auth_tokens()
        if not result:
            return
        
        guild = bot.get_guild(GUILD_ID)
        if not guild:
            return
        
        # Process refreshed users
        for user_data in result.get('refreshed', []):
            try:
                member = guild.get_member(int(user_data['discord_id']))
                if member:
                    # Format: [ALLIANCE] CORP | Name
                    alliance = user_data.get('alliance', '')
                    corp = user_data.get('corporation', '')
                    char_name = user_data.get('character_name', '')
                    
                    if alliance:
                        new_nickname = f"[{alliance}] {corp} | {char_name}"
                    else:
                        new_nickname = f"{corp} | {char_name}"
                    
                    # Update nickname if different
                    if member.nick != new_nickname:
                        await member.edit(nick=new_nickname)
                        await log_action(guild, f"Updated nickname for {member.name}: {new_nickname}", "INFO")
                        await asyncio.sleep(1)  # Rate limit
            except Exception as e:
                logger.error(f"Error updating nickname for {user_data['discord_id']}: {e}")
        
        # Send DM to users who failed to refresh
        for failed_user in result.get('failed', []):
            try:
                member = guild.get_member(int(failed_user['discord_id']))
                if member:
                    try:
                        await member.send(
                            "⚠️ Your Eve Online authentication has expired!\n\n"
                            f"Please use `/auth` in {guild.name} to re-authenticate and keep your nickname updated."
                        )
                        await log_action(guild, f"Sent reauth request to {member.name}", "WARNING")
                    except:
                        pass  # User has DMs disabled
            except Exception as e:
                logger.error(f"Error notifying {failed_user['discord_id']}: {e}")
                
    except Exception as e:
        logger.error(f"Error in update_nicknames task: {e}")

@update_nicknames.before_loop
async def before_update_nicknames():
    """Wait until bot is ready before starting nickname updater"""
    await bot.wait_until_ready()

# ----------------------------
# Welcome Message
# ----------------------------
@bot.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.text_channels, name="recruitment")
    if channel:
        await channel.send(
            f"👋 Welcome to **Rev3nants Wrath**, {member.mention}!\n\n"
            f"If you're looking to join up, type **/recruit**.\n\n"
            f"If you need to speak with leadership or a diplomat, type **/officer**."
        )
        await log_action(member.guild, f"{member.name} joined the server.", "INFO")

# ----------------------------
# /recruit Command (5 min cooldown)
# ----------------------------
@bot.tree.command(
    name="recruit",
    description="Open a private recruitment thread (available to everyone).",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.checks.cooldown(1, 300.0, key=lambda i: i.user.id)
async def recruit(interaction: discord.Interaction):
    guild = interaction.guild
    channel = interaction.channel
    thread_name = f"Recruit-{interaction.user.name}"

    # Prevent duplicate threads (case-insensitive) - check both active and archived
    try:
        # Check active threads
        for thread in channel.threads:
            if thread.name.lower() == thread_name.lower():
                await interaction.response.send_message(
                    "❌ You already have an open recruit thread.", ephemeral=True
                )
                return
        
        # Check archived threads
        async for thread in channel.archived_threads(limit=100):
            if thread.name.lower() == thread_name.lower():
                await interaction.response.send_message(
                    "❌ You already have a recruit thread (it may be archived). Please contact a recruiter.", ephemeral=True
                )
                return
    except discord.Forbidden:
        await log_action(guild, "Cannot check archived threads - missing permissions", "WARNING")

    # Respond immediately to prevent interaction timeout
    await interaction.response.send_message(
        "✅ Creating your recruitment thread...", ephemeral=True
    )

    try:
        # Create private thread
        thread = await channel.create_thread(
            name=thread_name,
            type=discord.ChannelType.private_thread,
            invitable=False
        )

        # Add the user to the thread so they can see it
        await thread.add_user(interaction.user)

        # Ping Recruiter role directly
        recruiter_role = guild.get_role(RECRUITER_ROLE_ID)
        if recruiter_role:
            # Add all members with recruiter role to thread (with rate limiting)
            for member in recruiter_role.members:
                try:
                    await thread.add_user(member)
                    await asyncio.sleep(0.5)  # Rate limit: 500ms delay between additions
                except discord.HTTPException as e:
                    await log_action(guild, f"Failed to add {member.name} to thread: {e}", "WARNING")
        else:
            await log_action(guild, "Recruiter role not found", "WARNING")
        
        welcome_message = (
            f"{recruiter_role.mention if recruiter_role else ''}\n"
            f"👋 {interaction.user.mention} has started a recruitment thread!\n\n"
            "We're glad you're interested in joining us! To get started, auth all your characters that "
            "you're going to recruit into the corporation with our alliance here: "
            "https://auth.black-rose.space\n\n"
            "Once that's finished, reply back here and let us know your in-game names that you registered. "
            "While you're at it, tell us a little bit about yourself!"
        )

        await thread.send(welcome_message)
        await log_action(guild, f"{interaction.user} created recruitment thread {thread.name}.", "INFO")
    except discord.Forbidden:
        await interaction.followup.send("❌ I don't have permission to create threads.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to create thread: {e}", ephemeral=True)
        print(f"Thread creation error: {e}")

# ----------------------------
# /officer Command (10 min cooldown)
# ----------------------------
@bot.tree.command(
    name="officer",
    description="Open a private thread for officer discussion (or escalate from recruiter).",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.checks.cooldown(1, 600.0, key=lambda i: i.user.id)
async def officer(interaction: discord.Interaction):
    guild = interaction.guild
    channel = interaction.channel
    
    # Check if user has Recruiter or Director role
    recruiter_role = guild.get_role(RECRUITER_ROLE_ID)
    director_role = guild.get_role(DIRECTOR_ROLE_ID)
    
    if not (recruiter_role in interaction.user.roles or director_role in interaction.user.roles):
        await interaction.response.send_message(
            "❌ You need the Recruiter or Director role to use this command.", ephemeral=True
        )
        return
    
    thread_name = f"officer-{interaction.user.name}"

    # Prevent duplicate threads (case-insensitive) - check both active and archived
    try:
        # Check active threads
        for thread in channel.threads:
            if thread.name.lower() == thread_name.lower():
                await interaction.response.send_message(
                    "❌ You already have an open officer thread.", ephemeral=True
                )
                return
        
        # Check archived threads
        async for thread in channel.archived_threads(limit=100):
            if thread.name.lower() == thread_name.lower():
                await interaction.response.send_message(
                    "❌ You already have an officer thread (it may be archived). Please contact a director.", ephemeral=True
                )
                return
    except discord.Forbidden:
        await log_action(guild, "Cannot check archived threads - missing permissions", "WARNING")

    await interaction.response.send_message(
        "✅ Creating your officer thread...", ephemeral=True
    )

    try:
        thread = await channel.create_thread(
            name=thread_name,
            type=discord.ChannelType.private_thread,
            invitable=False
        )

        # Add the user to the thread so they can see it
        await thread.add_user(interaction.user)

        # Ping Director role directly
        director_role = guild.get_role(DIRECTOR_ROLE_ID)
        if director_role:
            # Add all members with director role to thread (with rate limiting)
            for member in director_role.members:
                try:
                    await thread.add_user(member)
                    await asyncio.sleep(0.5)  # Rate limit: 500ms delay between additions
                except discord.HTTPException as e:
                    await log_action(guild, f"Failed to add {member.name} to thread: {e}", "WARNING")
        else:
            await log_action(guild, "Director role not found", "WARNING")

        welcome_message = (
            f"{director_role.mention if director_role else ''}\n"
            f"👋 {interaction.user.mention} has started a thread for officer discussion."
        )

        await thread.send(welcome_message)
        await log_action(guild, f"{interaction.user} created officer thread {thread.name}.", "INFO")
    except discord.Forbidden:
        await interaction.followup.send("❌ I don't have permission to create threads.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to create thread: {e}", ephemeral=True)
        print(f"Thread creation error: {e}")

# ----------------------------
# /close Command (Directors only)
# ----------------------------
@bot.tree.command(
    name="close",
    description="Close the current thread. (Directors only)",
    guild=discord.Object(id=GUILD_ID)
)
async def close(interaction: discord.Interaction):
    # Check if user has director role by ID
    if not any(role.id == DIRECTOR_ROLE_ID for role in interaction.user.roles):
        await interaction.response.send_message(
            "❌ You don't have permission to use this command.", ephemeral=True
        )
        return

    thread = interaction.channel
    if isinstance(thread, discord.Thread):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Remove all users except those with Recruiter or Director roles
            removed_count = 0
            for member in thread.members:
                # Skip bots and users with staff roles
                if member.bot:
                    continue
                has_staff_role = any(role.id in [RECRUITER_ROLE_ID, DIRECTOR_ROLE_ID] for role in member.roles)
                if not has_staff_role:
                    try:
                        await thread.remove_user(member)
                        removed_count += 1
                        await asyncio.sleep(0.5)  # Rate limit
                    except discord.HTTPException as e:
                        await log_action(interaction.guild, f"Failed to remove {member.name} from thread: {e}", "WARNING")
            
            # Now archive and lock the thread
            await thread.edit(archived=True, locked=True)
            await interaction.followup.send(f"🗂️ Thread closed. Removed {removed_count} user(s).", ephemeral=True)
            await log_action(interaction.guild, f"{interaction.user} closed thread {thread.name} (removed {removed_count} users).", "INFO")
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I don't have permission to manage this thread.", ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error closing thread: {str(e)}", ephemeral=True
            )
            await log_action(interaction.guild, f"Error closing thread {thread.name}: {e}", "ERROR")
    else:
        await interaction.response.send_message(
            "⚠️ This command can only be used inside a thread.", ephemeral=True
        )

# ----------------------------
# /remind Command (Directors only)
# ----------------------------
@bot.tree.command(
    name="remind",
    description="Set a reminder. (Directors only)",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(days="Days until reminder", hours="Hours until reminder", minutes="Minutes until reminder", message="Reminder message")
async def remind(interaction: discord.Interaction, days: int = 0, hours: int = 0, minutes: int = 0, message: str = "Reminder!"):
    # Check if user has director role by ID
    if not any(role.id == DIRECTOR_ROLE_ID for role in interaction.user.roles):
        await interaction.response.send_message(
            "❌ You don't have permission to use this command.", ephemeral=True
        )
        return

    total_seconds = days * 86400 + hours * 3600 + minutes * 60
    if total_seconds <= 0:
        await interaction.response.send_message("⚠️ Please specify a valid time.", ephemeral=True)
        return
    
    # Calculate reminder time
    reminder_time = datetime.now() + timedelta(seconds=total_seconds)
    
    # Store reminder in database
    result = await add_reminder(
        guild_id=interaction.guild.id,
        channel_id=interaction.channel.id,
        user_id=interaction.user.id,
        reminder_time=reminder_time,
        message=message
    )
    
    if result:
        await interaction.response.send_message(
            f"⏰ Reminder set for {days}d {hours}h {minutes}m from now.", ephemeral=True
        )
        await log_action(interaction.guild, f"{interaction.user} set a reminder for {days}d {hours}h {minutes}m: {message}", "INFO")
    else:
        await interaction.response.send_message(
            "❌ Failed to create reminder. Please try again.", ephemeral=True
        )

# ----------------------------
# /remove Command (Recruiters and Directors only)
# ----------------------------
@bot.tree.command(
    name="remove",
    description="Remove a user from the current thread. (Recruiters and Directors only)",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(user="The user to remove from the thread (optional - removes command user if not specified)")
async def remove(interaction: discord.Interaction, user: discord.Member = None):
    # Check if user has recruiter or director role
    has_permission = any(role.id in [RECRUITER_ROLE_ID, DIRECTOR_ROLE_ID] for role in interaction.user.roles)
    if not has_permission:
        await interaction.response.send_message(
            "❌ You don't have permission to use this command.", ephemeral=True
        )
        return

    thread = interaction.channel
    if not isinstance(thread, discord.Thread):
        await interaction.response.send_message(
            "⚠️ This command can only be used inside a thread.", ephemeral=True
        )
        return
    
    # If no user specified, remove the command user
    target_user = user if user else interaction.user
    
    # Prevent removing staff members (unless they're removing themselves)
    is_staff = any(role.id in [RECRUITER_ROLE_ID, DIRECTOR_ROLE_ID] for role in target_user.roles)
    if is_staff and target_user != interaction.user:
        await interaction.response.send_message(
            "❌ You cannot remove staff members from threads.", ephemeral=True
        )
        return
    
    # Check if user is in the thread
    if target_user not in thread.members:
        await interaction.response.send_message(
            f"⚠️ {target_user.mention} is not in this thread.", ephemeral=True
        )
        return
    
    try:
        await thread.remove_user(target_user)
        await interaction.response.send_message(
            f"✅ Removed {target_user.mention} from the thread.", ephemeral=True
        )
        await log_action(interaction.guild, f"{interaction.user} removed {target_user.name} from thread {thread.name}.", "INFO")
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I don't have permission to remove users from this thread.", ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            f"❌ Failed to remove user: {str(e)}", ephemeral=True
        )
        await log_action(interaction.guild, f"Error removing {target_user.name} from thread: {e}", "ERROR")

# ----------------------------
# /threads Command (Recruiters and Directors only)
# ----------------------------
@bot.tree.command(
    name="threads",
    description="List all recruitment and officer threads. (Recruiters and Directors only)",
    guild=discord.Object(id=GUILD_ID)
)
async def threads(interaction: discord.Interaction):
    # Check if user has recruiter or director role
    has_permission = any(role.id in [RECRUITER_ROLE_ID, DIRECTOR_ROLE_ID] for role in interaction.user.roles)
    if not has_permission:
        await interaction.response.send_message(
            "❌ You don't have permission to use this command.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)
    
    guild = interaction.guild
    active_threads = []
    archived_threads = []
    
    try:
        # Get all text channels
        for channel in guild.text_channels:
            # Check active threads
            for thread in channel.threads:
                if thread.name.lower().startswith(("recruit-", "officer-")):
                    active_threads.append(thread)
            
            # Check archived threads (last 50)
            try:
                async for thread in channel.archived_threads(limit=50):
                    if thread.name.lower().startswith(("recruit-", "officer-")):
                        archived_threads.append(thread)
            except discord.Forbidden:
                pass
        
        # Build response
        embed = discord.Embed(
            title="📋 Thread List",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        if active_threads:
            active_list = "\n".join([f"• {thread.mention} - {thread.member_count} members" for thread in active_threads[:10]])
            if len(active_threads) > 10:
                active_list += f"\n*...and {len(active_threads) - 10} more*"
            embed.add_field(name=f"🟢 Active Threads ({len(active_threads)})", value=active_list, inline=False)
        else:
            embed.add_field(name="🟢 Active Threads", value="*No active threads*", inline=False)
        
        if archived_threads:
            archived_list = "\n".join([f"• {thread.name} - Archived <t:{int(thread.archive_timestamp.timestamp())}:R>" for thread in archived_threads[:10]])
            if len(archived_threads) > 10:
                archived_list += f"\n*...and {len(archived_threads) - 10} more*"
            embed.add_field(name=f"📦 Recently Archived ({len(archived_threads)})", value=archived_list, inline=False)
        else:
            embed.add_field(name="📦 Recently Archived", value="*No archived threads*", inline=False)
        
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error retrieving threads: {str(e)}", ephemeral=True)
        logger.error(f"Error in /threads command: {e}")

# ----------------------------
# /reopen Command (Directors only)
# ----------------------------
@bot.tree.command(
    name="reopen",
    description="Reopen an archived thread. (Directors only)",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(thread_name="The name of the thread to reopen (e.g., Recruit-Username)")
async def reopen(interaction: discord.Interaction, thread_name: str):
    # Check if user has director role
    if not any(role.id == DIRECTOR_ROLE_ID for role in interaction.user.roles):
        await interaction.response.send_message(
            "❌ You don't have permission to use this command.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)
    
    guild = interaction.guild
    found_thread = None
    
    try:
        # Search for the thread in archived threads
        for channel in guild.text_channels:
            try:
                async for thread in channel.archived_threads(limit=100):
                    if thread.name.lower() == thread_name.lower():
                        found_thread = thread
                        break
            except discord.Forbidden:
                continue
            
            if found_thread:
                break
        
        if not found_thread:
            await interaction.followup.send(
                f"❌ Could not find archived thread: `{thread_name}`", ephemeral=True
            )
            return
        
        # Unarchive the thread
        await found_thread.edit(archived=False, locked=False)
        await interaction.followup.send(
            f"✅ Reopened thread: {found_thread.mention}", ephemeral=True
        )
        await log_action(guild, f"{interaction.user} reopened thread {found_thread.name}.", "INFO")
        
    except discord.Forbidden:
        await interaction.followup.send(
            "❌ I don't have permission to unarchive threads.", ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(
            f"❌ Error reopening thread: {str(e)}", ephemeral=True
        )
        logger.error(f"Error in /reopen command: {e}")

# ----------------------------
# /list-reminders Command
# ----------------------------
@bot.tree.command(
    name="list-reminders",
    description="List your pending reminders.",
    guild=discord.Object(id=GUILD_ID)
)
async def list_reminders(interaction: discord.Interaction):
    # Directors can see all reminders, others see only their own
    is_director = any(role.id == DIRECTOR_ROLE_ID for role in interaction.user.roles)
    
    if is_director:
        reminders = await get_all_reminders(interaction.guild.id)
        if not reminders:
            await interaction.response.send_message("📭 No pending reminders in this server.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="⏰ All Pending Reminders",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        
        for reminder in reminders[:15]:
            reminder_id = reminder['id']
            user_id = reminder['user_id']
            reminder_time = reminder['reminder_time']
            message = reminder['message']
            
            user = interaction.guild.get_member(user_id)
            user_name = user.mention if user else f"User ID: {user_id}"
            reminder_dt = datetime.fromisoformat(reminder_time)
            time_str = f"<t:{int(reminder_dt.timestamp())}:R>"
            embed.add_field(
                name=f"ID: {reminder_id} - {user_name}",
                value=f"{message[:100]}\nDue: {time_str}",
                inline=False
            )
        
        if len(reminders) > 15:
            embed.set_footer(text=f"Showing 15 of {len(reminders)} reminders")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        reminders = await get_user_reminders(interaction.user.id)
        if not reminders:
            await interaction.response.send_message("📭 You have no pending reminders.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="⏰ Your Pending Reminders",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        
        for reminder in reminders:
            reminder_id = reminder['id']
            reminder_time = reminder['reminder_time']
            message = reminder['message']
            
            reminder_dt = datetime.fromisoformat(reminder_time)
            time_str = f"<t:{int(reminder_dt.timestamp())}:R>"
            embed.add_field(
                name=f"ID: {reminder_id}",
                value=f"{message[:100]}\nDue: {time_str}",
                inline=False
            )
        
        embed.set_footer(text=f"Use /cancel-reminder <id> to cancel")
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ----------------------------
# /cancel-reminder Command
# ----------------------------
@bot.tree.command(
    name="cancel-reminder",
    description="Cancel a pending reminder.",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(reminder_id="The ID of the reminder to cancel")
async def cancel_reminder(interaction: discord.Interaction, reminder_id: int):
    is_director = any(role.id == DIRECTOR_ROLE_ID for role in interaction.user.roles)
    
    # Get reminder to check ownership
    user_reminders = await get_user_reminders(interaction.user.id)
    all_reminders = await get_all_reminders(interaction.guild.id) if is_director else []
    
    # Check if reminder exists
    reminder_found = False
    reminder_user_id = None
    
    for reminder in user_reminders:
        if reminder['id'] == reminder_id:
            reminder_found = True
            reminder_user_id = interaction.user.id
            break
    
    if not reminder_found and is_director:
        for reminder in all_reminders:
            if reminder['id'] == reminder_id:
                reminder_found = True
                reminder_user_id = reminder['user_id']
                break
    
    if not reminder_found:
        await interaction.response.send_message(
            f"❌ Reminder ID {reminder_id} not found.", ephemeral=True
        )
        return
    
    # Check if user owns the reminder or is a director
    if reminder_user_id != interaction.user.id and not is_director:
        await interaction.response.send_message(
            "❌ You can only cancel your own reminders.", ephemeral=True
        )
        return
    
    # Delete the reminder
    await delete_reminder(reminder_id)
    await interaction.response.send_message(
        f"✅ Cancelled reminder ID {reminder_id}.", ephemeral=True
    )
    await log_action(interaction.guild, f"{interaction.user} cancelled reminder ID {reminder_id}.", "INFO")

# ----------------------------
# /auth Command
# ----------------------------
@bot.tree.command(
    name="auth",
    description="Authenticate with Eve Online SSO to update your Discord nickname.",
    guild=discord.Object(id=GUILD_ID)
)
async def auth(interaction: discord.Interaction):
    try:
        # Create auth URL
        auth_url = await create_auth_url(interaction.user.id, interaction.user.name)
        
        if not auth_url:
            await interaction.response.send_message(
                "❌ Failed to create authentication link. Please try again later.", ephemeral=True
            )
            return
        
        # Send auth link via DM
        try:
            await interaction.user.send(
                f"🔐 **Eve Online Authentication**\n\n"
                f"Click the link below to authenticate your Eve Online character:\n"
                f"{auth_url}\n\n"
                f"This will allow the bot to:\n"
                f"• Update your Discord nickname to match your Eve character\n"
                f"• Display your Alliance and Corporation info\n\n"
                f"The link is unique to you and expires after use."
            )
            await interaction.response.send_message(
                "✅ Authentication link sent to your DMs!", ephemeral=True
            )
            await log_action(interaction.guild, f"{interaction.user} requested Eve SSO authentication", "INFO")
        except discord.Forbidden:
            # If DMs are disabled, send in channel (ephemeral)
            await interaction.response.send_message(
                f"🔐 **Eve Online Authentication**\n\n"
                f"Click here to authenticate: {auth_url}\n\n"
                f"⚠️ Enable DMs to receive auth links privately in the future.", 
                ephemeral=True
            )
    except Exception as e:
        await interaction.response.send_message(
            f"❌ Error creating authentication link: {str(e)}", ephemeral=True
        )
        logger.error(f"Error in /auth command: {e}")

# ----------------------------
# /status Command (Directors only)
# ----------------------------
@bot.tree.command(
    name="status",
    description="View Eve SSO authentication status for all users. (Directors only)",
    guild=discord.Object(id=GUILD_ID)
)
async def status(interaction: discord.Interaction):
    # Check if user has director role
    if not any(role.id == DIRECTOR_ROLE_ID for role in interaction.user.roles):
        await interaction.response.send_message(
            "❌ You don't have permission to use this command.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)
    
    try:
        auth_users = await get_all_auth_users()
        guild = interaction.guild
        
        # Get all guild members
        authenticated = []
        needs_reauth = []
        not_authenticated = []
        
        now = datetime.now()
        
        for user_data in auth_users:
            member = guild.get_member(int(user_data['discord_id']))
            if member:
                token_expires = datetime.fromisoformat(user_data['token_expires_at'])
                if token_expires < now:
                    needs_reauth.append((member, user_data))
                else:
                    authenticated.append((member, user_data))
        
        # Find members who haven't authenticated
        all_member_ids = {str(m.id) for m in guild.members if not m.bot}
        auth_member_ids = {u['discord_id'] for u in auth_users}
        unauth_ids = all_member_ids - auth_member_ids
        
        for member_id in unauth_ids:
            member = guild.get_member(int(member_id))
            if member:
                not_authenticated.append(member)
        
        # Build embed
        embed = discord.Embed(
            title="🔐 Eve SSO Authentication Status",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        if authenticated:
            auth_list = []
            for member, data in authenticated[:15]:
                alliance = f"[{data['eve_alliance_ticker']}] " if data.get('eve_alliance_ticker') else ""
                corp = data.get('eve_corporation_ticker', 'N/A')
                char = data.get('eve_character_name', 'N/A')
                auth_list.append(f"✅ {member.mention} - {alliance}{corp} | {char}")
            
            embed.add_field(
                name=f"🟢 Authenticated ({len(authenticated)})",
                value="\n".join(auth_list) if auth_list else "*None*",
                inline=False
            )
            if len(authenticated) > 15:
                embed.add_field(name="", value=f"*...and {len(authenticated) - 15} more*", inline=False)
        
        if needs_reauth:
            reauth_list = []
            for member, data in needs_reauth[:10]:
                char = data.get('eve_character_name', 'N/A')
                reauth_list.append(f"⚠️ {member.mention} - {char} (expired)")
            
            embed.add_field(
                name=f"🟡 Needs Re-authentication ({len(needs_reauth)})",
                value="\n".join(reauth_list) if reauth_list else "*None*",
                inline=False
            )
        
        if not_authenticated:
            unauth_list = [f"❌ {member.mention}" for member in not_authenticated[:20]]
            embed.add_field(
                name=f"🔴 Not Authenticated ({len(not_authenticated)})",
                value="\n".join(unauth_list) if unauth_list else "*None*",
                inline=False
            )
            if len(not_authenticated) > 20:
                embed.add_field(name="", value=f"*...and {len(not_authenticated) - 20} more*", inline=False)
        
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error retrieving status: {str(e)}", ephemeral=True)
        logger.error(f"Error in /status command: {e}")

# ----------------------------
# Error Handler
# ----------------------------
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CommandOnCooldown):
        remaining = int(error.retry_after)
        minutes, seconds = divmod(remaining, 60)
        await interaction.response.send_message(
            f"⏳ You can use this command again in **{minutes}m {seconds}s**.", ephemeral=True
        )
    else:
        logger.error(f"Unexpected error: {error}")
        try:
            await interaction.response.send_message("⚠️ An unexpected error occurred.", ephemeral=True)
        except:
            pass  # Interaction might have already expired

# ----------------------------
# Run the bot
# ----------------------------
bot.run(TOKEN)