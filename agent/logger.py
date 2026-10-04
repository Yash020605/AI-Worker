"""
Centralised logging setup using loguru.
"""
import os
import sys
from loguru import logger

from agent.config import config

# Ensure log directory exists
os.makedirs(os.path.dirname(config.LOG_FILE) if os.path.dirname(config.LOG_FILE) else "logs", exist_ok=True)

# Remove default handler
logger.remove()

# Console — colourful, human-readable
logger.add(
    sys.stderr,
    level=config.LOG_LEVEL,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> — <level>{message}</level>",
    colorize=True,
)

# File — full detail
logger.add(
    config.LOG_FILE,
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} — {message}",
    rotation="10 MB",
    retention="7 days",
    compression="zip",
)

__all__ = ["logger"]
