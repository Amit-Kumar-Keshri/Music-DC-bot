import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import yt_dlp
import asyncio
import requests

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Per-guild music queues
guild_queues = {}

# Volume control (per guild)
guild_volumes = {}

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

# Update play_next to use volume
async def play_next(ctx):
    queue = guild_queues.get(ctx.guild.id, [])
    if not queue:
        await ctx.send("Gaane khatam ja rahi hu main.")
        await ctx.voice_client.disconnect()
        return
    song = queue[0]
    ffmpeg_options = {'options': '-vn -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'}
    # Use url for high quality direct stream
    source = discord.FFmpegPCMAudio(song['url'], **ffmpeg_options)
    volume = get_volume(ctx.guild.id)
    source = discord.PCMVolumeTransformer(source, volume=volume)
    def after_playing(error):
        if error:
            print(f'Player error: {error}')
        fut = asyncio.run_coroutine_threadsafe(handle_next(ctx), bot.loop)
        try:
            fut.result()
        except Exception as e:
            print(f'Error in after_playing: {e}')
    ctx.voice_client.play(source, after=after_playing)
    await ctx.send(f"Now playing: {song['title']}")

def ensure_queue(guild_id):
    if guild_id not in guild_queues:
        guild_queues[guild_id] = []

def remove_first_from_queue(guild_id):
    if guild_id in guild_queues and guild_queues[guild_id]:
        guild_queues[guild_id].pop(0)

async def handle_next(ctx):
    remove_first_from_queue(ctx.guild.id)
    await play_next(ctx)

@bot.command()
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
        await ctx.send(f"Joined {channel}")
    else:
        await ctx.send("You are not in a voice channel!")

# Playlist support in play command
@bot.command(aliases=['p'])
async def play(ctx, *, query):
    ensure_queue(ctx.guild.id)
    await ctx.send(f"Fetching audio for: {query}")
    try:
        ydl_opts = {
            'format': 'bestaudio[ext=webm][acodec=opus]/bestaudio[ext=m4a]/bestaudio/best',
            'quiet': True,
            'extract_flat': False,
            'noplaylist': False,
            'default_search': 'ytsearch',  # This enables search by name
            'source_address': '0.0.0.0',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            entries = info['entries'] if 'entries' in info else [info]
            songs = []
            for entry in entries:
                if entry:
                    songs.append({'title': entry.get('title', 'Unknown'), 'url': entry['url'], 'webpage_url': entry.get('webpage_url', query)})
    except Exception as e:
        await ctx.send(f"Error fetching audio: {e}")
        return
    guild_queues[ctx.guild.id].extend(songs)
    if ctx.voice_client is None:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
        else:
            await ctx.send("You are not in a voice channel!")
            return
    if not ctx.voice_client.is_playing():
        await play_next(ctx)
    else:
        await ctx.send(f"Added to queue: {', '.join(song['title'] for song in songs)}")

@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        guild_queues.pop(ctx.guild.id, None)
        await ctx.send("Disconnected!")
    else:
        await ctx.send("I'm not in a voice channel!")

@bot.command()
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("Playback paused.")
    else:
        await ctx.send("Nothing is playing right now.")

@bot.command()
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("Playback resumed.")
    else:
        await ctx.send("Nothing is paused.")

@bot.command()
async def stop(ctx):
    if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
        ctx.voice_client.stop()
        guild_queues[ctx.guild.id] = []
        await ctx.send("Playback stopped and queue cleared.")
    else:
        await ctx.send("Nothing is playing or paused.")

@bot.command()
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Skipped to next song.")
    else:
        await ctx.send("Nothing is playing to skip.")

@bot.command()
async def volume(ctx, vol: float):
    if not 0 < vol <= 2:
        await ctx.send("Volume must be between 0.1 and 2.0")
        return
    set_volume(ctx.guild.id, vol)
    await ctx.send(f"Volume set to {vol}")
    if ctx.voice_client and ctx.voice_client.source:
        ctx.voice_client.source.volume = vol

# Lyrics command using lyrics.ovh
@bot.command()
async def lyrics(ctx, *, query=None):
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

@bot.command(aliases=["q"])
async def queue(ctx):
    queue = guild_queues.get(ctx.guild.id, [])
    if not queue:
        await ctx.send("The queue is empty.")
        return
    msg = "**Current Queue:**\n"
    for i, song in enumerate(queue):
        if i == 0:
            msg += f"Now Playing: {song['title']}\n"
        else:
            msg += f"{i}. {song['title']} \n"
    await ctx.send(msg)

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
        "!skip — Skip to next song\n"
        "!queue or !q — Show queue\n"
        "!volume <0.1-2.0> — Set playback volume\n"
        "!lyrics [song name] — Get lyrics for current or given song\n"
        "!leave — Leave the voice channel\n"
        "!helpme — Show this help message"
    )
    await ctx.send(msg)

bot.run(TOKEN) 