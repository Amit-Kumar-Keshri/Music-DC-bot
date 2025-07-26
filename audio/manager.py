"""
Audio management for Music Bot
Handles audio sources, playback, and queue management
"""
import asyncio
import discord
import yt_dlp
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from config import config
from utils.logger import logger, log_audio_event
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials


@dataclass
class Song:
    """Enhanced song data structure"""
    title: str
    url: Optional[str] = None
    webpage_url: Optional[str] = None
    duration: Optional[int] = None
    thumbnail: Optional[str] = None
    requester_id: int = 0
    is_lazy: bool = False
    added_at: datetime = field(default_factory=datetime.now)
    
    def format_duration(self) -> str:
        """Format duration as MM:SS or HH:MM:SS"""
        if not self.duration:
            return "?"
        try:
            seconds = int(self.duration)
            m, s = divmod(seconds, 60)
            h, m = divmod(m, 60)
            if h > 0:
                return f"{h}:{m:02d}:{s:02d}"
            return f"{m}:{s:02d}"
        except (ValueError, TypeError):
            return "?"


class AudioManager:
    """Manages audio operations for the bot"""
    
    def __init__(self):
        self.guild_queues: Dict[int, List[Song]] = {}
        self.guild_current_index: Dict[int, int] = {}
        self.guild_volumes: Dict[int, float] = {}
        self.repeat_flags: Dict[int, bool] = {}
        self.alone_timers: Dict[int, asyncio.Task] = {}
        
        # Initialize Spotify client if credentials are available
        self.spotify_client = None
        if config.spotify_client_id and config.spotify_client_secret:
            try:
                auth_manager = SpotifyClientCredentials(
                    client_id=config.spotify_client_id,
                    client_secret=config.spotify_client_secret
                )
                self.spotify_client = Spotify(auth_manager=auth_manager)
                logger.info("Spotify integration initialized successfully")
            except Exception as e:
                logger.error("spotify_init", e)
    
    def ensure_queue(self, guild_id: int):
        """Ensure guild has a queue initialized"""
        if guild_id not in self.guild_queues:
            self.guild_queues[guild_id] = []
        if guild_id not in self.guild_current_index:
            self.guild_current_index[guild_id] = 0
        if guild_id not in self.guild_volumes:
            self.guild_volumes[guild_id] = config.default_volume
    
    def get_queue(self, guild_id: int) -> List[Song]:
        """Get queue for a guild"""
        self.ensure_queue(guild_id)
        return self.guild_queues[guild_id]
    
    def get_current_song(self, guild_id: int) -> Optional[Song]:
        """Get currently playing song"""
        queue = self.get_queue(guild_id)
        current_idx = self.guild_current_index.get(guild_id, 0)
        
        if queue and 0 <= current_idx < len(queue):
            return queue[current_idx]
        return None
    
    def add_songs(self, guild_id: int, songs: List[Song]) -> int:
        """Add songs to queue and return starting position"""
        self.ensure_queue(guild_id)
        queue_length_before = len(self.guild_queues[guild_id])
        
        self.guild_queues[guild_id].extend(songs)
        
        # Handle current_index logic
        current_idx = self.guild_current_index.get(guild_id, 0)
        
        if queue_length_before == 0:
            # Queue was empty, start from beginning
            self.guild_current_index[guild_id] = 0
        
        return queue_length_before
    
    def remove_song(self, guild_id: int, index: int) -> Optional[Song]:
        """Remove song at index from queue"""
        queue = self.get_queue(guild_id)
        
        if 0 <= index < len(queue):
            removed_song = queue.pop(index)
            
            # Adjust current index if necessary
            current_idx = self.guild_current_index.get(guild_id, 0)
            if index <= current_idx and current_idx > 0:
                self.guild_current_index[guild_id] = current_idx - 1
            
            return removed_song
        return None
    
    def move_song(self, guild_id: int, from_idx: int, to_idx: int) -> bool:
        """Move song from one position to another"""
        queue = self.get_queue(guild_id)
        
        if not (0 <= from_idx < len(queue) and 0 <= to_idx < len(queue)):
            return False
        
        song = queue.pop(from_idx)
        queue.insert(to_idx, song)
        
        # Adjust current index if necessary
        current_idx = self.guild_current_index.get(guild_id, 0)
        
        if from_idx == current_idx:
            self.guild_current_index[guild_id] = to_idx
        elif from_idx < current_idx <= to_idx:
            self.guild_current_index[guild_id] = current_idx - 1
        elif to_idx <= current_idx < from_idx:
            self.guild_current_index[guild_id] = current_idx + 1
        
        return True
    
    def shuffle_queue(self, guild_id: int):
        """Shuffle the queue (except currently playing song)"""
        queue = self.get_queue(guild_id)
        
        if len(queue) <= 1:
            return
        
        current_idx = self.guild_current_index.get(guild_id, 0)
        
        if current_idx < len(queue):
            # Remove currently playing song
            current_song = queue.pop(current_idx)
            
            # Shuffle remaining songs
            import random
            random.shuffle(queue)
            
            # Put current song back at the beginning
            queue.insert(0, current_song)
            self.guild_current_index[guild_id] = 0
    
    def clear_queue(self, guild_id: int):
        """Clear the entire queue"""
        self.guild_queues[guild_id] = []
        self.guild_current_index[guild_id] = 0
    
    def set_volume(self, guild_id: int, volume: float):
        """Set volume for a guild"""
        self.guild_volumes[guild_id] = max(config.min_volume, min(config.max_volume, volume))
    
    def get_volume(self, guild_id: int) -> float:
        """Get volume for a guild"""
        return self.guild_volumes.get(guild_id, config.default_volume)
    
    def set_repeat(self, guild_id: int, repeat: bool):
        """Set repeat flag for a guild"""
        self.repeat_flags[guild_id] = repeat
    
    def is_repeat(self, guild_id: int) -> bool:
        """Check if repeat is enabled for a guild"""
        return self.repeat_flags.get(guild_id, False)
    
    def jump_to_song(self, guild_id: int, index: int) -> bool:
        """Jump to a specific song in the queue"""
        queue = self.get_queue(guild_id)
        
        if 0 <= index < len(queue):
            self.guild_current_index[guild_id] = index
            return True
        return False
    
    def next_song(self, guild_id: int) -> bool:
        """Move to next song, return True if successful"""
        queue = self.get_queue(guild_id)
        current_idx = self.guild_current_index.get(guild_id, 0)
        
        if current_idx < len(queue) - 1:
            self.guild_current_index[guild_id] = current_idx + 1
            return True
        return False
    
    def previous_song(self, guild_id: int) -> bool:
        """Move to previous song, return True if successful"""
        current_idx = self.guild_current_index.get(guild_id, 0)
        
        if current_idx > 0:
            self.guild_current_index[guild_id] = current_idx - 1
            return True
        return False
    
    async def resolve_lazy_song(self, song: Song) -> Song:
        """Resolve a lazy-loaded song to get actual audio URL"""
        if not song.is_lazy:
            return song
        
        try:
            ydl_opts = config.ydl_options.copy()
            search_query = song.webpage_url or song.title
            
            if not self._is_http_url(search_query):
                ydl_opts['default_search'] = 'ytsearch1'
            
            def _extract_info():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(search_query, download=False)
                    if 'entries' in info and info['entries']:
                        info = info['entries'][0]
                    return info
            
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, _extract_info)
            
            # Update song with resolved information
            song.url = info['url']
            song.title = info.get('title', song.title)
            song.duration = info.get('duration', song.duration)
            song.thumbnail = info.get('thumbnail', song.thumbnail)
            
            if not song.webpage_url or not song.webpage_url.startswith('http'):
                song.webpage_url = info.get('webpage_url', song.webpage_url)
            
            song.is_lazy = False
            
            log_audio_event(0, "song_resolved", song.title)
            return song
            
        except Exception as e:
            logger.error("resolve_lazy_song", e, song_title=song.title)
            raise
    
    async def get_spotify_tracks(self, url: str) -> List[Song]:
        """Extract tracks from Spotify URL"""
        if not self.spotify_client:
            return []
        
        tracks = []
        
        try:
            if 'track' in url:
                track = self.spotify_client.track(url)
                search_query = f"{track['name']} {track['artists'][0]['name']} official audio"
                tracks.append(Song(
                    title=f"{track['name']} - {track['artists'][0]['name']}",
                    webpage_url=search_query,
                    duration=track.get('duration_ms', 0) // 1000,
                    is_lazy=True
                ))
                
            elif 'playlist' in url:
                results = self.spotify_client.playlist_tracks(url)
                for item in results['items']:
                    track = item['track']
                    if track:
                        search_query = f"{track['name']} {track['artists'][0]['name']} official audio"
                        tracks.append(Song(
                            title=f"{track['name']} - {track['artists'][0]['name']}",
                            webpage_url=search_query,
                            duration=track.get('duration_ms', 0) // 1000,
                            is_lazy=True
                        ))
                        
            elif 'album' in url:
                results = self.spotify_client.album_tracks(url)
                for track in results['items']:
                    search_query = f"{track['name']} {track['artists'][0]['name']} official audio"
                    tracks.append(Song(
                        title=f"{track['name']} - {track['artists'][0]['name']}",
                        webpage_url=search_query,
                        duration=track.get('duration_ms', 0) // 1000,
                        is_lazy=True
                    ))
                    
        except Exception as e:
            logger.error("get_spotify_tracks", e)
        
        return tracks
    
    def _is_http_url(self, url: str) -> bool:
        """Check if string is an HTTP URL"""
        return url.startswith(('http://', 'https://'))
    
    def _is_spotify_url(self, url: str) -> bool:
        """Check if string is a Spotify URL"""
        return 'open.spotify.com' in url
    
    async def create_audio_source(self, song: Song, guild_id: int) -> discord.AudioSource:
        """Create discord audio source from song"""
        if song.is_lazy:
            song = await self.resolve_lazy_song(song)
        
        if not song.url:
            raise ValueError(f"No playable URL found for {song.title}")
        
        # Create FFmpeg source with optimized options
        source = discord.FFmpegPCMAudio(song.url, **config.ffmpeg_options)
        
        # Apply volume
        volume = self.get_volume(guild_id)
        source = discord.PCMVolumeTransformer(source, volume=volume)
        
        return source
    
    # Auto-disconnect and timer management
    def is_bot_alone_in_vc(self, guild) -> bool:
        """Check if bot is alone in voice channel"""
        if not guild.voice_client or not guild.voice_client.channel:
            return False
        
        human_members = [
            member for member in guild.voice_client.channel.members 
            if not member.bot
        ]
        return len(human_members) == 0
    
    async def start_alone_timer(self, guild):
        """Start timer to leave if bot stays alone"""
        guild_id = guild.id
        
        # Cancel existing timer
        if guild_id in self.alone_timers:
            self.alone_timers[guild_id].cancel()
        
        async def alone_timer():
            try:
                await asyncio.sleep(config.alone_timeout)
                
                if self.is_bot_alone_in_vc(guild) and guild.voice_client:
                    # Find text channel to send message
                    text_channel = guild.system_channel
                    if not text_channel:
                        for channel in guild.text_channels:
                            if channel.permissions_for(guild.me).send_messages:
                                text_channel = channel
                                break
                    
                    # Disconnect and clean up
                    await guild.voice_client.disconnect()
                    self.clear_queue(guild_id)
                    
                    if text_channel:
                        await text_channel.send(
                            "🚪 Left voice channel - no one was listening. "
                            "I'll be back when you need me! 👋"
                        )
                    
                    log_audio_event(guild_id, "auto_disconnect_alone")
                    
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error("alone_timer", e, guild_id=guild_id)
            finally:
                self.alone_timers.pop(guild_id, None)
        
        self.alone_timers[guild_id] = asyncio.create_task(alone_timer())
    
    def cancel_alone_timer(self, guild_id: int):
        """Cancel the alone timer"""
        if guild_id in self.alone_timers:
            self.alone_timers[guild_id].cancel()
            self.alone_timers.pop(guild_id, None)


# Global audio manager instance
audio_manager = AudioManager() 