"""Centralized configuration settings for the trading bot."""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # LLM Configuration
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    OLLAMA_MODEL: str = "kimi-k2.5:cloud"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"  # For RAG vector store
    LLM_TEMPERATURE: float = 0.0
    LLM_TIMEOUT: int = 120

    # API Keys
    FMP_API_KEY: str = ""  # Financial Modeling Prep (legacy - optional)
    NEWS_DATA_API_KEY: str = ""  # NewsData.io (free tier: 200 req/day)
    NEWS_API_KEY: str = ""  # NewsAPI.org (optional)

    # Discord Integration
    DISCORD_BOT_TOKEN: str = ""
    DISCORD_WEBHOOK_URL: str = ""
    DISCORD_ALERT_CHANNEL_ID: int = 0

    # Trading Parameters (stored as string, parsed as list)
    DEFAULT_TICKERS: str = "GC=F,SI=F,PL=F,PA=F,DX-Y.NYB"
    CONFIDENCE_THRESHOLD: float = 0.7
    STOP_LOSS_PERCENTAGE: float = 0.02  # 2%
    TAKE_PROFIT_PERCENTAGE: float = 0.04  # 4%

    # Alert Auto-Monitoring Configuration
    ALERT_MODE_ENABLED: bool = False
    ALERT_INTERVAL_MINUTES: int = 15
    ALERT_HOURS_START: int = 9
    ALERT_HOURS_END: int = 17
    ALERT_DAYS_START: int = 1
    ALERT_DAYS_END: int = 5
    ALERT_ONLY_NEW_SIGNALS: bool = True

    # Signal Performance Tracking Configuration
    PERFORMANCE_TRACKING_ENABLED: bool = True
    PERFORMANCE_DATA_FILE: str = "./data/signal_performance.json"
    SIGNAL_HOLDING_TIMEOUT_MINUTES: int = 240  # Auto-close after 4h

    # RAG/Vector Store Configuration
    CHROMA_PERSIST_DIR: str = "./vectorstore/chroma_db"
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    TOP_K_RETRIEVAL: int = 5

    # Analysis Parameters
    RSI_PERIOD: int = 14
    RSI_OVERBOUGHT: float = 70.0
    RSI_OVERSOLD: float = 30.0
    SMA_PERIOD: int = 200
    VIX_FEAR_THRESHOLD: float = 20.0
    US_YIELD_HIGH_THRESHOLD: float = 4.0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Parse env vars as strings, let validators handle complex types
        env_parse_none_str = ""
        env_parse_enums = False


def parse_tickers(tickers_str: str) -> List[str]:
    """Parse comma-separated ticker string into list."""
    return [t.strip() for t in tickers_str.split(',') if t.strip()]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
