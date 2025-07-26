"""
Music Bot
A feature-rich Discord music bot with modular architecture
"""
import asyncio
import discord
from discord.ext import commands
from config import config
from utils.logger import logger
from audio.manager import audio_manager


class MusicBot(commands.Bot):
    """Enhanced Discord bot with improved architecture"""
    
    def __init__(self):
        # Use fixed prefix since we no longer have database settings
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True  # For voice state monitoring
        
        super().__init__(
            command_prefix=config.default_prefix,
            intents=intents,
            help_command=None  # We'll create our own help command
        )
        
        # Store startup time
        self.startup_time = None
    
    async def setup_hook(self):
        """Initialize bot components"""
        logger.info("Starting bot setup...")
        
        try:
            # Load all command cogs
            await self.load_extension('commands.music')
            await self.load_extension('commands.admin')
            
            logger.info("All command modules loaded successfully")
            logger.info("Bot setup completed successfully")
            
        except Exception as e:
            logger.error("setup_hook", e)
            raise
    
    async def on_ready(self):
        """Bot ready event"""
        self.startup_time = discord.utils.utcnow()
        
        logger.info(f"Bot is ready! Logged in as {self.user.name} ({self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")
        logger.info(f"Serving {sum(guild.member_count for guild in self.guilds)} users")
        
        # Set bot status
        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name=f"music in {len(self.guilds)} servers | {config.default_prefix}help"
        )
        await self.change_presence(activity=activity)
    
    async def on_guild_join(self, guild):
        """Handle bot joining a new guild"""
        logger.info(f"Joined new guild: {guild.name} ({guild.id}) with {guild.member_count} members")
        
        # Find a channel to send welcome message
        welcome_channel = None
        if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
            welcome_channel = guild.system_channel
        else:
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    welcome_channel = channel
                    break
        
        if welcome_channel:
            embed = discord.Embed(
                title="🎵 Thanks for adding Music Bot!",
                description=(
                    f"I'm ready to play music in **{guild.name}**!\n\n"
                    f"🎮 **Get started:** `{config.default_prefix}play <song name>`\n"
                    f"📋 **See all commands:** `{config.default_prefix}help`\n\n"
                    "🎵 **Features:**\n"
                    "• YouTube & Spotify support\n"
                    "• Interactive player controls\n"
                    "• Queue management\n"
                    "• High-quality audio\n"
                    "• Multi-server support"
                ),
                color=0x2b2d31
            )
            embed.set_thumbnail(url=self.user.display_avatar.url)
            try:
                await welcome_channel.send(embed=embed)
            except Exception as e:
                logger.error("guild_join_welcome", e, guild_id=guild.id)
    
    async def on_guild_remove(self, guild):
        """Handle bot leaving a guild"""
        logger.info(f"Left guild: {guild.name} ({guild.id})")
        
        # Clean up guild data
        try:
            audio_manager.clear_queue(guild.id)
            audio_manager.cancel_alone_timer(guild.id)
            
        except Exception as e:
            logger.error("guild_leave_cleanup", e, guild_id=guild.id)
    
    async def on_voice_state_update(self, member, before, after):
        """Monitor voice channel changes for auto-leave functionality"""
        try:
            guild = member.guild
            
            # Only process if bot is in a voice channel
            if not guild.voice_client or not guild.voice_client.channel:
                return
            
            bot_channel = guild.voice_client.channel
            
            # Check if the change affects the bot's channel
            member_was_in_bot_channel = before.channel == bot_channel
            member_is_in_bot_channel = after.channel == bot_channel
            
            if member_was_in_bot_channel or member_is_in_bot_channel:
                # Someone joined or left the bot's channel
                if audio_manager.is_bot_alone_in_vc(guild):
                    # Bot is now alone, start timer
                    await audio_manager.start_alone_timer(guild)
                else:
                    # Bot is not alone, cancel any existing timer
                    audio_manager.cancel_alone_timer(guild.id)
                    
        except Exception as e:
            logger.error("voice_state_update", e, guild_id=member.guild.id)
    
    async def on_command_error(self, ctx, error):
        """Global command error handler"""
        # Ignore command not found errors
        if isinstance(error, commands.CommandNotFound):
            return
        
        # Handle cooldown errors
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏱️ Command is on cooldown. Try again in {error.retry_after:.1f} seconds.")
            return
        
        # Handle missing permissions
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command!")
            return
        
        # Handle bot missing permissions
        if isinstance(error, commands.BotMissingPermissions):
            missing_perms = ", ".join(error.missing_permissions)
            await ctx.send(f"❌ I need the following permissions: {missing_perms}")
            return
        
        # Handle other command errors
        if isinstance(error, commands.CommandError):
            await ctx.send(f"❌ Command error: {str(error)}")
            logger.error("command_error", error, guild_id=ctx.guild.id if ctx.guild else None)
            return
        
        # Log unexpected errors
        logger.error("unexpected_command_error", error, guild_id=ctx.guild.id if ctx.guild else None)
        await ctx.send("❌ An unexpected error occurred. The error has been logged.")
    
    async def close(self):
        """Clean shutdown of the bot"""
        logger.info("Bot is shutting down...")
        
        try:
            # Clean up all voice connections
            for guild in self.guilds:
                if guild.voice_client:
                    audio_manager.clear_queue(guild.id)
                    audio_manager.cancel_alone_timer(guild.id)
                    await guild.voice_client.disconnect()
            
            logger.info("Bot shutdown completed")
            
        except Exception as e:
            logger.error("bot_shutdown", e)
        
        await super().close()


# Help command implementation
@commands.command(name='help')
async def help_command(ctx):
    """Enhanced help command with beautiful formatting"""
    embed = discord.Embed(
        title="🎵 Music Bot Commands",
        description="Complete guide to all available commands",
        color=0x2b2d31
    )
    
    # Basic Controls
    embed.add_field(
        name="🎮 **Basic Controls**",
        value=(
            "`join` — Join your voice channel\n"
            "`play <song/URL>` (alias: `p`) — Play music\n"
            "`pause` — Pause current song\n"
            "`resume` — Resume playback\n"
            "`stop` — Stop and clear queue\n"
            "`leave` — Leave voice channel"
        ),
        inline=False
    )
    
    # Navigation & Queue
    embed.add_field(
        name="⏭️ **Navigation & Queue**",
        value=(
            "`skip` (alias: `next`) — Skip current song\n"
            "`jump <number>` — Jump to specific song\n"
            "`queue` (alias: `q`) — Show current queue\n"
            "`shuffle` — Shuffle the queue\n"
            "`repeat` — Toggle repeat current song\n"
            "`remove <number>` — Remove song from queue\n"
            "`move <from> <to>` — Move song position"
        ),
        inline=False
    )
    
    # Audio & Settings
    embed.add_field(
        name="🔧 **Audio & Settings**",
        value=(
            "`volume <0.1-2.0>` — Set playback volume\n"
            "`stats` — Show server song statistics (Admin)\n"
            "`forceleave` — Force disconnect (Admin)\n"
            "`clearqueue` — Clear entire queue (Admin)"
        ),
        inline=False
    )
    
    embed.add_field(
        name="💡 **Tips**",
        value=(
            f"• Use `{config.default_prefix}` as the command prefix\n"
            "• Click the buttons on the player for quick controls\n"
            "• Supports YouTube links, playlists, and Spotify URLs\n"
            "• I'll auto-leave if alone for 1 minute\n"
            "• Queue supports up to hundreds of songs!"
        ),
        inline=False
    )
    
    embed.set_footer(
        text=f"Bot made with ❤️ | Currently in {len(ctx.bot.guilds)} servers",
        icon_url=ctx.bot.user.display_avatar.url
    )
    
    await ctx.send(embed=embed)


async def main():
    """Main bot startup function"""
    try:
        # Create bot instance
        bot = MusicBot()
        
        # Add the help command
        bot.add_command(help_command)
        
        # Start the bot
        logger.info("Starting Music Bot...")
        await bot.start(config.discord_token)
        
    except Exception as e:
        logger.error("bot_startup", e)
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error("main_execution", e)
        print(f"Fatal error: {e}") 