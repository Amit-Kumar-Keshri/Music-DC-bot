"""
Enhanced logging utilities for Music Bot
"""
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from config import config


class BotLogger:
    """Enhanced logger with structured logging and proper error handling"""
    
    def __init__(self, name: str = "MusicBot"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Create logs directory if it doesn't exist
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # File handler for errors
        error_handler = logging.FileHandler(
            log_dir / "bot_errors.log", 
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        error_handler.setFormatter(error_formatter)
        
        # File handler for general logs
        info_handler = logging.FileHandler(
            log_dir / "bot_info.log",
            encoding='utf-8'
        )
        info_handler.setLevel(logging.INFO)
        info_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        info_handler.setFormatter(info_formatter)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        
        # Add handlers
        self.logger.addHandler(error_handler)
        self.logger.addHandler(info_handler)
        self.logger.addHandler(console_handler)
    
    def info(self, message: str, **kwargs):
        """Log info message with optional context"""
        if kwargs:
            message = f"{message} | Context: {kwargs}"
        self.logger.info(message)
    
    def error(self, context: str, error: Exception, **kwargs):
        """Log error with context and additional information"""
        error_msg = f"[{context}] {str(error)}"
        if kwargs:
            error_msg += f" | Additional info: {kwargs}"
        self.logger.error(error_msg, exc_info=True)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with optional context"""
        if kwargs:
            message = f"{message} | Context: {kwargs}"
        self.logger.warning(message)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with optional context"""
        if kwargs:
            message = f"{message} | Context: {kwargs}"
        self.logger.debug(message)


# Global logger instance
logger = BotLogger()


def log_command_usage(ctx, command_name: str, args: Optional[str] = None):
    """Log command usage for analytics"""
    guild_info = f"Guild: {ctx.guild.name} ({ctx.guild.id})" if ctx.guild else "DM"
    user_info = f"User: {ctx.author.name}#{ctx.author.discriminator} ({ctx.author.id})"
    command_info = f"Command: {command_name}"
    if args:
        command_info += f" Args: {args}"
    
    logger.info(f"Command used | {guild_info} | {user_info} | {command_info}")


def log_audio_event(guild_id: int, event: str, song_title: Optional[str] = None):
    """Log audio-related events"""
    message = f"Audio event: {event} | Guild: {guild_id}"
    if song_title:
        message += f" | Song: {song_title}"
    logger.info(message)


def log_error_with_context(context: str, error: Exception, guild_id: Optional[int] = None, user_id: Optional[int] = None):
    """Log error with additional context"""
    additional_info = {}
    if guild_id:
        additional_info['guild_id'] = guild_id
    if user_id:
        additional_info['user_id'] = user_id
    
    logger.error(context, error, **additional_info) 