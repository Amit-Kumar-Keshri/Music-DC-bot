"""
Configuration management for Music Bot
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class BotConfig:
    """Main bot configuration"""
    # Discord settings
    discord_token: str
    default_prefix: str = '!'
    
    # Audio settings
    default_volume: float = 0.5
    max_volume: float = 2.0
    min_volume: float = 0.1
    idle_timeout: int = 300  # 5 minutes
    alone_timeout: int = 60   # 1 minute
    
    # Spotify settings
    spotify_client_id: Optional[str] = None
    spotify_client_secret: Optional[str] = None
    
    # File paths
    error_log_file: str = 'bot_errors.log'
    
    # Audio quality settings
    ffmpeg_options: dict = None
    ydl_options: dict = None
    
    # UI settings
    queue_per_page: int = 10
    search_results_limit: int = 10
    
    # Rate limiting
    command_cooldown: float = 1.0
    api_request_delay: float = 0.1
    
    def __post_init__(self):
        """Initialize default options after dataclass creation"""
        if self.ffmpeg_options is None:
            self.ffmpeg_options = {
                'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                'options': '-vn'
            }
        
        if self.ydl_options is None:
            self.ydl_options = {
                'format': 'bestaudio[ext=webm][acodec=opus]/bestaudio[ext=m4a]/bestaudio/best',
                'quiet': True,
                'extract_flat': False,
                'noplaylist': True,
                'default_search': 'ytsearch',
                'source_address': '0.0.0.0',
            }


def load_config() -> BotConfig:
    """Load configuration from environment variables"""
    from dotenv import load_dotenv
    load_dotenv()
    
    discord_token = os.getenv('DISCORD_TOKEN')
    if not discord_token:
        raise ValueError("DISCORD_TOKEN environment variable is required")
    
    return BotConfig(
        discord_token=discord_token,
        spotify_client_id=os.getenv('SPOTIFY_CLIENT_ID'),
        spotify_client_secret=os.getenv('SPOTIPY_CLIENT_SECRET'),
        default_prefix=os.getenv('DEFAULT_PREFIX', '!'),
        default_volume=float(os.getenv('DEFAULT_VOLUME', '0.5')),
        idle_timeout=int(os.getenv('IDLE_TIMEOUT', '300')),
        alone_timeout=int(os.getenv('ALONE_TIMEOUT', '60')),
    )


# Global config instance
config = load_config() 