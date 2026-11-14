"""
Configuration management for VAMIKA (NISAR-based flood & wetland monitoring application).
Supports MOCK, LOCAL, API, and CLOUD data modes.
"""

import os
from pathlib import Path
from enum import Enum


class DataMode(str, Enum):
    """Data ingestion mode."""
    MOCK = "MOCK"
    LOCAL = "LOCAL"
    API = "API"
    CLOUD = "CLOUD"


class Config:
    """Application configuration."""

    # Data Mode
    DATA_MODE = DataMode(os.getenv("DATA_MODE", "MOCK"))
    DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
    
    # API Configuration
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", 8000))
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    
    # ASF Credentials (for API mode)
    ASF_USERNAME = os.getenv("ASF_USERNAME", "")
    ASF_PASSWORD = os.getenv("ASF_PASSWORD", "")
    
    # Processing
    MAX_SUBSET_PIXELS = int(os.getenv("MAX_SUBSET_PIXELS", 15_000_000))
    DEFAULT_BOUNDS = (41.30, 12.70, 41.35, 12.75)
    
    # NISAR Parameters
    NISAR_PROCESSING_LEVEL = "GCOV"
    NISAR_DATASET = "NISAR"
    NISAR_PRODUCTION_CONFIG = "PR"
    NISAR_DATA_MATURITY = "PROVISIONAL"
    SUPPORTED_POLARIZATIONS = ("HHHH", "HVHV", "VVVV", "HHHV", "VHVH", "VVVH")
    
    # Flood Detection Thresholds (dB)
    DEFAULT_FLOOD_CHANGE_THRESHOLD = -2.0
    DEFAULT_LOW_BACKSCATTER_THRESHOLD = -15.0
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = Path(os.getenv("LOG_FILE", "./logs/app.log"))


def get_config() -> Config:
    """Get application configuration."""
    return Config()
