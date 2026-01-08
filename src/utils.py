"""
Shared utilities for GTA Risky Driving Stats project.
"""

import logging
from pathlib import Path

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Data directories
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
DATA_ANALYSIS = PROJECT_ROOT / "data" / "analysis"

# Output directories
OUTPUT_FIGURES = PROJECT_ROOT / "output" / "figures"
OUTPUT_TABLES = PROJECT_ROOT / "output" / "tables"


def setup_logging(name: str, level: int = logging.INFO) -> logging.Logger:
    """Set up a logger with console output."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(level)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def ensure_dirs():
    """Ensure all data and output directories exist."""
    for dir_path in [DATA_RAW, DATA_PROCESSED, DATA_ANALYSIS, OUTPUT_FIGURES, OUTPUT_TABLES]:
        dir_path.mkdir(parents=True, exist_ok=True)


# Game release dates (hardcoded fallback)
GAME_RELEASES = {
    "GTA V": {
        "console": "2013-09-17",
        "pc": "2015-04-14",
        "steam_app_id": 271590,
    },
    "Elden Ring": {
        "pc": "2022-02-25",
        "steam_app_id": 1245620,
    },
    "Halo Infinite": {
        "pc": "2021-12-08",
        "steam_app_id": 1240440,
    },
    "Fallout 4": {
        "pc": "2015-11-10",
        "steam_app_id": 377160,
    },
    "Skyrim": {
        "pc": "2011-11-11",
        "steam_app_id": 72850,
    },
}

# NYC Open Data endpoints
NYC_REDLIGHT_ENDPOINT = "https://data.cityofnewyork.us/resource/jrqf-3d3i.json"
NYC_SPEED_ENDPOINT = "https://data.cityofnewyork.us/resource/hazs-r364.json"  # School speed camera

# Chicago Data Portal endpoints
CHICAGO_SPEED_ENDPOINT = "https://data.cityofchicago.org/resource/hhkd-xvj4.json"
CHICAGO_REDLIGHT_ENDPOINT = "https://data.cityofchicago.org/resource/spqx-js37.json"
