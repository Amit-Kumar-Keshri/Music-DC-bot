import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import yt_dlp
import asyncio
import requests
from discord import Embed, ui
import json
from discord.ext.commands import has_role, CheckFailure
import logging
from datetime import datetime
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Per-guild music queues
guild_queues = {}

# Per-guild current song index
guild_current_index = {}

# Per-guild UI messages
guild_ui_messages = {}

# Volume control (per guild)
guild_volumes = {}

# Repeat state per guild
repeat_flags = {}

# --- Per-guild settings ---
SETTINGS_FILE = 'guild_settings.json'
def load_settings():
    try:
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def save_settings(settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f)

guild_settings = load_settings()

def get_guild_prefix(guild_id):
    return guild_settings.get(str(guild_id), {}).get('prefix', '!')

def set_guild_prefix(guild_id, prefix):
    if str(guild_id) not in guild_settings:
        guild_settings[str(guild_id)] = {}
    guild_settings[str(guild_id)]['prefix'] = prefix
    save_settings(guild_settings)

def get_guild_volume(guild_id):
    return guild_settings.get(str(guild_id), {}).get('volume', 0.5)

def set_guild_volume(guild_id, volume):
    if str(guild_id) not in guild_settings:
        guild_settings[str(guild_id)] = {}
    guild_settings[str(guild_id)]['volume'] = volume
    save_settings(guild_settings)

# --- Custom prefix support ---
def get_prefix(bot, message):
    if message.guild:
        return get_guild_prefix(message.guild.id)
    return '!'

bot.command_prefix = get_prefix

# --- Auto-disconnect after idle ---
IDLE_TIMEOUT = 300  # seconds (5 minutes)
async def auto_disconnect(ctx):
    await asyncio.sleep(IDLE_TIMEOUT)
    if ctx.voice_client and not ctx.voice_client.is_playing():
        await ctx.voice_client.disconnect()
        await ctx.send("Disconnected due to inactivity.")

# Helper to get audio source from YouTube Music
async def get_audio_source(url):
    ydl_opts = {
        'format': 'bestaudio[ext=webm][acodec=opus]/bestaudio[ext=m4a]/bestaudio/best',
        'quiet': True,
        'extract_flat': False,
        'noplaylist': True,
        'default_search': 'ytsearch',
        'source_address': '0.0.0.0',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if 'entries' in info:
            info = info['entries'][0]
        return {'title': info.get('title', 'Unknown'), 'url': info['url'], 'webpage_url': info.get('webpage_url', url)}

def get_volume(guild_id):
    return guild_volumes.get(guild_id, 0.5)

def set_volume(guild_id, value):
    guild_volumes[guild_id] = value

def format_duration(seconds):
    if not seconds:
        return "?"
    try:
        seconds = int(seconds)
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"
    except (ValueError, TypeError):
        return "?"

# Helper to check if a string is a Spotify URL
def is_spotify_url(url):
    return 'open.spotify.com' in url

def is_http_url(url):
    return url.startswith('http')

# Helper to get tracks from a Spotify playlist/album/track
async def get_spotify_tracks(url):
    tracks = []
    if not sp:
        return tracks

    try:
        if 'track' in url:
            track = sp.track(url)
            tracks.append(f"{track['name']} {track['artists'][0]['name']} official audio")
        elif 'playlist' in url:
            results = sp.playlist_tracks(url)
            for item in results['items']:
                t = item['track']
                if t:
                    tracks.append(f"{t['name']} {t['artists'][0]['name']} official audio")
        elif 'album' in url:
            results = sp.album_tracks(url)
            for t in results['items']:
                tracks.append(f"{t['name']} {t['artists'][0]['name']} official audio")
    except Exception as e:
        log_error('spotify_get_tracks', e)
        print(f"Error fetching from Spotify: {e}")

    return tracks

class NowPlayingView(ui.View):
    def __init__(self, ctx, bot):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.bot = bot
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        queue = guild_queues.get(self.ctx.guild.id, [])
        idx = guild_current_index.get(self.ctx.guild.id, 0)
        prev_enabled = idx > 0
        next_enabled = idx < len(queue) - 1
        previous_button = ui.Button(label="Prev", style=discord.ButtonStyle.grey, custom_id="previous", disabled=not prev_enabled)
        previous_button.callback = self.prev_song
        self.add_item(previous_button)

        if self.ctx.voice_client and self.ctx.voice_client.is_playing():
            play_pause_button = ui.Button(label="Pause", style=discord.ButtonStyle.blurple, custom_id="pause")
        else:
            play_pause_button = ui.Button(label="Play", style=discord.ButtonStyle.blurple, custom_id="resume")
        play_pause_button.callback = self.play_pause
        self.add_item(play_pause_button)
        
        skip_button = ui.Button(label="Next", style=discord.ButtonStyle.grey, custom_id="skip", disabled=not next_enabled)
        skip_button.callback = self.skip
        self.add_item(skip_button)

    async def prev_song(self, interaction: discord.Interaction):
        idx = guild_current_index.get(self.ctx.guild.id, 0)
        if idx > 0:
            await interaction.response.defer()
            # For previous song, set the index and directly call play_next
            # We need to stop the current song WITHOUT triggering after_playing callback
            guild_current_index[self.ctx.guild.id] = idx - 1
            if self.ctx.voice_client and (self.ctx.voice_client.is_playing() or self.ctx.voice_client.is_paused()):
                self.ctx.voice_client.stop()
            await play_next(self.ctx)
            return
        await interaction.response.send_message("No previous song.", ephemeral=True)

    async def play_pause(self, interaction: discord.Interaction):
        vc = self.ctx.voice_client
        if not vc:
            await interaction.response.send_message("I'm not in a voice channel.", ephemeral=True)
            return
        
        if vc.is_playing():
            vc.pause()
        elif vc.is_paused():
            vc.resume()
        else:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)
            return

        self.update_buttons()
        await interaction.response.edit_message(view=self)

    async def skip(self, interaction: discord.Interaction):
        queue = guild_queues.get(self.ctx.guild.id, [])
        idx = guild_current_index.get(self.ctx.guild.id, 0)
        if idx < len(queue) - 1:
            await interaction.response.defer()
            # For next song, just stop current song and let handle_next() do the work
            if self.ctx.voice_client and self.ctx.voice_client.is_playing():
                self.ctx.voice_client.stop()  # This will trigger after_playing -> handle_next()
            else:
                # If nothing is playing, manually advance and play
                guild_current_index[self.ctx.guild.id] = idx + 1
                await play_next(self.ctx)
            return
        await interaction.response.send_message("No next song.", ephemeral=True)

class QueueView(ui.View):
    def __init__(self, ctx, bot, songs, per_page=10):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.bot = bot
        self.songs = songs
        self.per_page = per_page
        self.current_page = 0
        self.total_pages = (len(self.songs) - 1) // self.per_page
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        prev_button = ui.Button(label="Prev", style=discord.ButtonStyle.grey, custom_id="prev_page", disabled=(self.current_page == 0))
        prev_button.callback = self.prev_page
        self.add_item(prev_button)

        next_button = ui.Button(label="Next", style=discord.ButtonStyle.grey, custom_id="next_page", disabled=(self.current_page >= self.total_pages))
        next_button.callback = self.next_page
        self.add_item(next_button)

    async def get_page_embed(self):
        start_index = self.current_page * self.per_page
        end_index = start_index + self.per_page
        description_lines = []
        idx = guild_current_index.get(self.ctx.guild.id, 0)
        for i, song in enumerate(self.songs[start_index:end_index], start=start_index):
            title = song.get('title', 'Unknown Title')
            if len(title) > 55:
                title = title[:52] + '...'
            prefix = '▶️ ' if (i + 1) == (idx + 1) else ''
            description_lines.append(f"{prefix}**{i + 1}.** {title}")
        description = "\n".join(description_lines)
        embed = Embed(title="Queue", description=description, color=0x2b2d31)
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages + 1}")
        return embed

    async def prev_page(self, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            embed = await self.get_page_embed()
            await interaction.response.edit_message(embed=embed, view=self)

    async def next_page(self, interaction: discord.Interaction):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.update_buttons()
            embed = await self.get_page_embed()
            await interaction.response.edit_message(embed=embed, view=self)

# Set up error logging
logging.basicConfig(filename='bot_errors.log', level=logging.ERROR, format='%(asctime)s %(levelname)s %(message)s')

def log_error(context, error):
    logging.error(f"[{context}] {error}")

# Update play_next to catch and report errors
import json
STATS_FILE = 'stats.json'

def load_stats():
    try:
        with open(STATS_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {'songs_played': 0, 'guild_queues': {}, 'most_played': {}}

def save_stats(stats):
    with open(STATS_FILE, 'w') as f:
        json.dump(stats, f)

stats = load_stats()

def update_stats_on_play(guild_id, song_title):
    stats['songs_played'] = stats.get('songs_played', 0) + 1
    stats['guild_queues'][str(guild_id)] = [s['title'] for s in guild_queues.get(guild_id, [])]
    if song_title:
        stats['most_played'][song_title] = stats['most_played'].get(song_title, 0) + 1
    save_stats(stats)

def update_stats_on_queue(guild_id):
    stats['guild_queues'][str(guild_id)] = [s['title'] for s in guild_queues.get(guild_id, [])]
    save_stats(stats)

# Update play_next to be more robust
async def play_next(ctx):
    try:
        queue = guild_queues.get(ctx.guild.id, [])
        idx = guild_current_index.get(ctx.guild.id, 0)
        
        # Check if we've reached the end of the queue or queue is empty
        if not queue or idx >= len(queue):
            # Clear UI when queue is finished
            ui_manager = UIManager(ctx)
            await ui_manager.update_ui()
            if not queue:
                await ctx.send("Gaane khatam, ja rahi hu main. Disconnecting in 5 minutes if nothing is added.")
                asyncio.create_task(auto_disconnect(ctx))
            return

        song = queue[idx]

        # If it's a lazy-loaded song, resolve it now
        if song.get('is_lazy'):
            try:
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'quiet': True,
                    'source_address': '0.0.0.0',
                }
                # For Spotify tracks, the webpage_url is a ytsearch query
                search_query = song['webpage_url']
                if not is_http_url(search_query):
                     ydl_opts['default_search'] = 'ytsearch1'

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(search_query, download=False)
                    # If search yields a list, take the first result
                    if 'entries' in info:
                        info = info['entries'][0]
                
                song['url'] = info['url']
                song['title'] = info.get('title', song.get('title', 'Unknown'))
                song['duration'] = info.get('duration', song.get('duration'))
                song['thumbnail'] = info.get('thumbnail')
                # For lazy-loaded YouTube tracks, the original URL is the webpage_url
                if not song.get('webpage_url').startswith('ytsearch'):
                    song['webpage_url'] = info.get('webpage_url', song.get('webpage_url'))
                song['is_lazy'] = False

            except Exception as e:
                log_error('lazy_resolve', e)
                await ctx.send(f"Sorry, I couldn't play `{song.get('title', 'a song')}`. It might be unavailable. Skipping.")
                await handle_next(ctx) # Skip to next
                return
        
        if not song.get('url'):
            await ctx.send(f"Could not find a playable URL for `{song.get('title')}`. Skipping.")
            await handle_next(ctx)
            return

        # Add reconnect options for stable streaming
        ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }
        source = discord.FFmpegPCMAudio(song['url'], **ffmpeg_options)
        volume = get_guild_volume(ctx.guild.id)
        source = discord.PCMVolumeTransformer(source, volume=volume)
        
        def after_playing(error):
            if error:
                print(f'Player error: {error}')
                log_error('after_playing', error)
            
            # Check if the bot is still in a voice channel before proceeding
            if ctx.voice_client:
                fut = asyncio.run_coroutine_threadsafe(handle_next(ctx), bot.loop)
                try:
                    fut.result()
                except Exception as e:
                    print(f'Error in after_playing: {e}')
                    log_error('after_playing_future', e)
            else:
                print("Bot is no longer in a voice channel. Can't play next song.")

        if ctx.voice_client:
            ctx.voice_client.play(source, after=after_playing)
        else:
            await ctx.send("I'm not in a voice channel anymore, so I can't play the song.")
            return # Stop execution if not in a voice channel
        
        ui_manager = UIManager(ctx)
        await ui_manager.update_ui()
        update_stats_on_play(ctx.guild.id, song['title'])
    except Exception as e:
        log_error('play_next', e)
        await ctx.send(f"Playback error: {e}. Trying next song.")
        await handle_next(ctx)

def ensure_queue(guild_id):
    if guild_id not in guild_queues:
        guild_queues[guild_id] = []

def remove_first_from_queue(guild_id):
    if guild_id in guild_queues and guild_queues[guild_id]:
        guild_queues[guild_id].pop(0)

async def update_player_ui(ctx):
    ui_manager = UIManager(ctx)
    await ui_manager.update_ui()

class UIManager:
    def __init__(self, ctx):
        self.ctx = ctx
        self.guild_id = ctx.guild.id

    async def update_ui(self):
        queue = guild_queues.get(self.guild_id, [])
        idx = guild_current_index.get(self.guild_id, 0)
        now_playing_message = guild_ui_messages.get(self.guild_id, {}).get('now_playing')
        queue_message = guild_ui_messages.get(self.guild_id, {}).get('queue')

        # --- Always delete old Now Playing message ---
        if now_playing_message:
            try:
                await now_playing_message.delete()
            except discord.NotFound:
                pass
            guild_ui_messages.get(self.guild_id, {}).pop('now_playing', None)
        now_playing_message = None

        # --- Always delete old Queue message ---
        if queue_message:
            try:
                await queue_message.delete()
            except discord.NotFound:
                pass
            guild_ui_messages.get(self.guild_id, {}).pop('queue', None)
        queue_message = None

        # --- Now Playing Message ---
        if queue and self.ctx.voice_client and (self.ctx.voice_client.is_playing() or self.ctx.voice_client.is_paused()):
            song = queue[idx]
            np_embed = Embed(title="Now Playing", description=song['title'], color=0x2b2d31)
            if 'thumbnail' in song:
                np_embed.set_thumbnail(url=song['thumbnail'])
            view = NowPlayingView(self.ctx, bot)
            now_playing_message = await self.ctx.send(embed=np_embed, view=view)
            if self.guild_id not in guild_ui_messages:
                guild_ui_messages[self.guild_id] = {}
            guild_ui_messages[self.guild_id]['now_playing'] = now_playing_message

        # --- Queue Message ---
        if queue:
            queue_view = QueueView(self.ctx, bot, queue)
            q_embed = await queue_view.get_page_embed()
            queue_message = await self.ctx.send(embed=q_embed, view=queue_view)
            if self.guild_id not in guild_ui_messages:
                guild_ui_messages[self.guild_id] = {}
            guild_ui_messages[self.guild_id]['queue'] = queue_message

async def handle_next(ctx):
    # Repeat logic
    if repeat_flags.get(ctx.guild.id, False):
        # Don't advance index, just replay current song
        await play_next(ctx)
    else:
        # Advance to next song by incrementing current_index
        queue = guild_queues.get(ctx.guild.id, [])
        idx = guild_current_index.get(ctx.guild.id, 0)
        if idx < len(queue) - 1:
            guild_current_index[ctx.guild.id] = idx + 1
            await play_next(ctx)
        else:
            # No more songs, clear the current index and stop
            guild_current_index[ctx.guild.id] = 0
            await ctx.send("Gaane khatam, ja rahi hu main. Disconnecting in 5 minutes if nothing is added.")
            asyncio.create_task(auto_disconnect(ctx))

@bot.command()
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
        await ctx.send(f"Joined {channel}")
    else:
        await ctx.send("You are not in a voice channel!")

# Update play command to only support YouTube and direct URLs
@bot.command(aliases=['p'])
async def play(ctx, *, query):
    ensure_queue(ctx.guild.id)
    songs = []

    if is_spotify_url(query):
        if not sp:
            await ctx.send("Spotify support is not configured. Please set credentials in your .env file.")
            return
        
        await ctx.send("Processing Spotify link... this may take a moment.")
        try:
            spotify_tracks = await get_spotify_tracks(query)
            if not spotify_tracks:
                await ctx.send("Couldn't find any tracks in that Spotify link.")
                return

            for track_query in spotify_tracks:
                # Add Spotify tracks lazily by their search query
                songs.append({
                    'webpage_url': track_query, # This will be used in a ytsearch
                    'title': track_query.replace(' official audio', ''),
                    'is_lazy': True
                })
        except Exception as e:
            log_error('spotify-processing', e)
            await ctx.send(f"Error processing Spotify link: {e}")
            return
        
        if not songs:
            await ctx.send("Could not prepare any tracks from that Spotify link.")
            return

    else:
        # await ctx.send(f"Fetching audio for: {query}")
        info = None
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'quiet': True,
                'extract_flat': 'in_playlist',
                'source_address': '0.0.0.0',
            }

            if is_http_url(query):
                # It's a URL. Check if it's a playlist.
                if 'list=' in query:
                    await ctx.send("YouTube Playlist detected, adding songs to the queue...")
                    ydl_opts['noplaylist'] = False # It is a playlist, process it.
                else:
                    ydl_opts['noplaylist'] = True # It's a single video URL, don't process playlist.
            else:
                # It's a search query.
                ydl_opts['default_search'] = 'ytsearch1'
                ydl_opts['noplaylist'] = True # For search, only get one video.


            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(query, download=False)
                entries = info['entries'] if 'entries' in info else [info]
                for entry in entries:
                    if entry:
                        songs.append({
                            'webpage_url': entry.get('webpage_url') or entry.get('url'),
                            'title': entry.get('title', 'Unknown'),
                            'duration': entry.get('duration'),
                            'is_lazy': True
                        })
        except Exception as e:
            log_error('play-yt', e)
            await ctx.send(f"Error fetching audio: {e}")
            return
        
    if not songs:
        await ctx.send("Couldn't find anything to add.")
        return

    guild_queues[ctx.guild.id].extend(songs)
    
    # Initialize current_index if this is the first song or if the queue was empty
    if len(guild_queues[ctx.guild.id]) == len(songs):
        guild_current_index[ctx.guild.id] = 0
    
    if ctx.voice_client is None:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
        else:
            await ctx.send("You are not in a voice channel!")
            return
            
    if not ctx.voice_client.is_playing():
        await play_next(ctx)
    else:
        # Avoid showing a huge list of songs
        if len(songs) > 1:
            await ctx.send(f"Added {len(songs)} songs to your queue.")
        else:
            await ctx.send(f"Added `{songs[0]['title']}` to your queue.")
            
    ui_manager = UIManager(ctx)
    await ui_manager.update_ui()
    update_stats_on_queue(ctx.guild.id)

@play.error
async def play_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("You need to provide a song name or URL! Usage: `!play <song name or URL>`")
    else:
        log_error('play_command', error)
        await ctx.send(f"An error occurred in the play command: {error}")

@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        guild_queues.pop(ctx.guild.id, None)
        ui_manager = UIManager(ctx)
        await ui_manager.update_ui()
        await ctx.send("Disconnected!")
    else:
        await ctx.send("I'm not in a voice channel!")
    update_stats_on_queue(ctx.guild.id)

@bot.command()
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("Playback paused.")
    else:
        await ctx.send("Nothing is playing right now.")
    update_stats_on_queue(ctx.guild.id)

@bot.command()
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("Playback resumed.")
    else:
        await ctx.send("Nothing is paused.")
    update_stats_on_queue(ctx.guild.id)

@bot.command()
async def stop(ctx):
    if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
        guild_queues[ctx.guild.id] = []
        ctx.voice_client.stop()
        ui_manager = UIManager(ctx)
        await ui_manager.update_ui()
        await ctx.send("Playback stopped and queue cleared.")
    else:
        await ctx.send("Nothing is playing or paused.")
    update_stats_on_queue(ctx.guild.id)

@bot.command(aliases=['next'])
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
    else:
        await ctx.send("Nothing is playing to skip.")
    update_stats_on_queue(ctx.guild.id)

@bot.command()
async def volume(ctx, vol: float):
    if not 0 < vol <= 2:
        await ctx.send("Volume must be between 0.1 and 2.0")
        return
    set_volume(ctx.guild.id, vol)
    await ctx.send(f"Volume set to {vol}")
    if ctx.voice_client and ctx.voice_client.source:
        ctx.voice_client.source.volume = vol
    update_stats_on_queue(ctx.guild.id)

# Lyrics command using lyrics.ovh
@bot.command()
async def lyricslyrics(ctx, *, query=None):
    if not query:
        queue = guild_queues.get(ctx.guild.id, [])
        if not queue:
            await ctx.send("No song is playing or specified.")
            return
        query = queue[0]['title']
    await ctx.send(f"Searching lyrics for: {query}")
    try:
        resp = requests.get(f'https://api.lyrics.ovh/v1/{query}')
        data = resp.json()
        if 'lyrics' in data and data['lyrics']:
            lyrics = data['lyrics']
            if len(lyrics) > 1900:
                await ctx.send(lyrics[:1900] + '...')
            else:
                await ctx.send(lyrics)
        else:
            await ctx.send("Lyrics not found.")
    except Exception as e:
        await ctx.send(f"Error fetching lyrics: {e}")
    update_stats_on_queue(ctx.guild.id)

# Update queue command to show duration
@bot.command(aliases=["q"])
async def queue(ctx):
    ui_manager = UIManager(ctx)
    await ui_manager.update_ui()
    update_stats_on_queue(ctx.guild.id)

@bot.command()
async def shuffle(ctx):
    queue = guild_queues.get(ctx.guild.id, [])
    if len(queue) > 1:
        import random
        now_playing = queue.pop(0)
        random.shuffle(queue)
        queue.insert(0, now_playing)
        await ctx.send("Queue shuffled!")
        ui_manager = UIManager(ctx)
        await ui_manager.update_ui()
    else:
        await ctx.send("Not enough songs in the queue to shuffle.")
    update_stats_on_queue(ctx.guild.id)

@bot.command()
async def remove(ctx, index: int):
    queue = guild_queues.get(ctx.guild.id, [])
    if len(queue) == 0:
        await ctx.send("Nothing to remove from the queue.")
        return
    if index < 1 or index > len(queue):
        await ctx.send(f"Index must be between 1 and {len(queue)}.")
        return
    if index == 1:
        # Remove currently playing (skip)
        ctx.voice_client.stop()
        await ctx.send(f"Skipped: {queue[0]['title']}")
    else:
        removed = queue.pop(index-1)
        await ctx.send(f"Removed: {removed['title']}")
    update_stats_on_queue(ctx.guild.id)

@bot.command()
async def move(ctx, from_idx: int, to_idx: int):
    queue = guild_queues.get(ctx.guild.id, [])
    if len(queue) <= 1:
        await ctx.send("Not enough songs in the queue to move.")
        return
    if from_idx < 1 or from_idx > len(queue) or to_idx < 1 or to_idx > len(queue):
        await ctx.send(f"Indexes must be between 1 and {len(queue)}.")
        return
    song = queue.pop(from_idx-1)
    queue.insert(to_idx-1, song)
    await ctx.send(f"Moved: {song['title']} to position {to_idx}")
    update_stats_on_queue(ctx.guild.id)

@bot.command()
async def repeat(ctx):
    flag = repeat_flags.get(ctx.guild.id, False)
    repeat_flags[ctx.guild.id] = not flag
    await ctx.send(f"Repeat is now {'ON' if not flag else 'OFF'}.")
    update_stats_on_queue(ctx.guild.id)

# Help command
@bot.command()
async def helpme(ctx):
    msg = (
        "**Music Bot Commands:**\n"
        "!join — Join your voice channel\n"
        "!play <song name or URL> — Play a song by name or URL, or a playlist\n"
        "!pause — Pause playback\n"
        "!resume — Resume playback\n"
        "!stop — Stop and clear queue\n"
        "!skip or !next — Skip to next song\n"
        "!queue or !q — Show queue\n"
        "!remove <n> — Remove song at position n (1 = now playing, 2 = next, etc.)\n"
        "!move <from> <to> — Move song from one position to another (1 = now playing)\n"
        "!shuffle — Shuffle the queue\n"
        "!repeat — Toggle repeat for current song\n"
        "!volume <0.1-2.0> — Set playback volume\n"
        "!lyrics [song name] — Get lyrics for current or given song\n"
        "!leave — Leave the voice channel\n"
        "!find or !search <query or URL> - Find songs or list tracks from a URL\n"
        "!helpme — Show this help message"
    )
    await ctx.send(msg)

# --- Song search and selection ---
@bot.command(aliases=['search'])
async def find(ctx, *, query):
    await ctx.send(f"Searching for: {query}")

    # Use flat extract for speed. It's just a search.
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'extract_flat': True,
        'source_address': '0.0.0.0',
    }

    info = None
    # If it's a URL (but not spotify), treat it as a direct source. Otherwise, search youtube.
    if is_http_url(query) and not is_spotify_url(query):
        ydl_opts['noplaylist'] = False
    else:
        ydl_opts['noplaylist'] = True
        ydl_opts['default_search'] = 'ytsearch10'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            
            entries = info.get('entries', [])
            if not entries:
                if info and 'title' in info: # single video result
                    entries = [info]
                else:
                    await ctx.send("No results found.")
                    return

            msg = "**Select a song by number:**\n"
            display_limit = 10
            display_count = min(len(entries), display_limit)

            for i, entry in enumerate(entries[:display_count]):
                dur = format_duration(entry.get('duration'))
                title = entry.get('title', 'Unknown')
                msg += f"{i+1}. [{dur}] {title}\n"
            
            if len(entries) > display_limit:
                msg += f"\n... and {len(entries) - display_limit} more."

            await ctx.send(msg)

            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit() and 1 <= int(m.content) <= display_count
            
            try:
                reply = await bot.wait_for('message', check=check, timeout=30)
                choice = int(reply.content) - 1
                song_to_add = entries[choice]
                
                ensure_queue(ctx.guild.id)
                
                # Add the chosen song lazily
                song_details = {
                    'title': song_to_add.get('title', 'Unknown'), 
                    'webpage_url': song_to_add.get('url'), # This is the webpage URL from flat extract
                    'duration': song_to_add.get('duration'),
                    'is_lazy': True,
                }
                guild_queues[ctx.guild.id].append(song_details)
                
                await ctx.send(f"Added to queue: [{format_duration(song_details.get('duration'))}] {song_details.get('title')}")
                
                if ctx.voice_client is None:
                    if ctx.author.voice:
                        await ctx.author.voice.channel.connect()
                    else:
                        await ctx.send("You are not in a voice channel!")
                        return
                
                if not ctx.voice_client.is_playing():
                    await play_next(ctx)
            
            except asyncio.TimeoutError:
                await ctx.send("No selection made. Cancelling.")
    except Exception as e:
        log_error('find-command', e)
        print(f"Error in find command: {e}")
        await ctx.send(f"An error occurred during search. It's possible the URL is unsupported or private.")
    
    update_stats_on_queue(ctx.guild.id)

# --- Commands to set prefix and default volume ---
@bot.command()
@commands.has_permissions(administrator=True)
async def setprefix(ctx, prefix: str):
    set_guild_prefix(ctx.guild.id, prefix)
    await ctx.send(f"Prefix set to: {prefix}")
    update_stats_on_queue(ctx.guild.id)

@bot.command()
@commands.has_permissions(administrator=True)
async def setvolume(ctx, vol: float):
    if not 0 < vol <= 2:
        await ctx.send("Volume must be between 0.1 and 2.0")
        return
    set_guild_volume(ctx.guild.id, vol)
    await ctx.send(f"Default volume set to {vol}")
    update_stats_on_queue(ctx.guild.id)

# Load Spotify credentials from .env
SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')

sp = None
if SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET:
    sp = Spotify(auth_manager=SpotifyClientCredentials(client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET))

bot.run(TOKEN) 