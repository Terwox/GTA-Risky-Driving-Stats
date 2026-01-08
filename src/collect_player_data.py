"""
Chunk 1: Collect player count data from Steam Charts.

Scrapes monthly player counts for GTA V and comparison games.
"""

import time
import requests
from bs4 import BeautifulSoup
import pandas as pd
from pathlib import Path

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import DATA_RAW, GAME_RELEASES, setup_logging, ensure_dirs

logger = setup_logging(__name__)

# Steam Charts URL pattern
STEAM_CHARTS_URL = "https://steamcharts.com/app/{app_id}"

# Request headers to avoid being blocked
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def scrape_steam_charts(app_id: int, game_name: str) -> pd.DataFrame:
    """
    Scrape monthly player data from Steam Charts for a given game.

    Args:
        app_id: Steam application ID
        game_name: Name of the game for the output

    Returns:
        DataFrame with columns: game, date, avg_players, peak_players
    """
    url = STEAM_CHARTS_URL.format(app_id=app_id)
    logger.info(f"Scraping {game_name} from {url}")

    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch data for {game_name}: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(response.text, "html.parser")

    # Find the data table - Steam Charts uses a table with class "common-table"
    table = soup.find("table", class_="common-table")
    if not table:
        logger.warning(f"No data table found for {game_name}")
        return pd.DataFrame()

    rows = []
    # Get all rows from the table (may or may not have tbody)
    all_rows = table.find_all("tr")

    for tr in all_rows:
        cells = tr.find_all("td")
        if len(cells) >= 5:
            # Columns: Month, Avg Players, Gain, % Gain, Peak Players
            month_str = cells[0].get_text(strip=True)
            avg_str = cells[1].get_text(strip=True)
            peak_str = cells[4].get_text(strip=True)

            # Skip "Last 30 Days" row - we want monthly data
            if "Last 30 Days" in month_str:
                continue

            # Parse numbers (remove commas, handle floats)
            try:
                # Parse as float first, then convert to int
                avg_players = int(float(avg_str.replace(",", "").replace("-", "0")))
                peak_players = int(float(peak_str.replace(",", "").replace("-", "0")))

                # Parse month (format: "November 2025")
                try:
                    date = pd.to_datetime(month_str, format="%B %Y")
                except ValueError:
                    # Try alternate format
                    try:
                        date = pd.to_datetime(month_str)
                    except ValueError:
                        logger.warning(f"Could not parse date: {month_str}")
                        continue

                rows.append({
                    "game": game_name,
                    "date": date,
                    "avg_players": avg_players,
                    "peak_players": peak_players,
                })
            except (ValueError, AttributeError) as e:
                logger.debug(f"Could not parse row: {e}")
                continue

    df = pd.DataFrame(rows)
    logger.info(f"Collected {len(df)} months of data for {game_name}")
    return df


def collect_all_player_data() -> pd.DataFrame:
    """
    Collect player data for all games defined in GAME_RELEASES.

    Returns:
        Combined DataFrame with all games' player data.
    """
    all_data = []

    for game_name, info in GAME_RELEASES.items():
        app_id = info.get("steam_app_id")
        if app_id:
            df = scrape_steam_charts(app_id, game_name)
            if not df.empty:
                all_data.append(df)
            # Be nice to the server
            time.sleep(1.5)

    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        combined = combined.sort_values(["game", "date"]).reset_index(drop=True)
        return combined

    return pd.DataFrame()


def main():
    """Main entry point for player data collection."""
    ensure_dirs()

    logger.info("Starting player data collection...")
    df = collect_all_player_data()

    if df.empty:
        logger.error("No data collected!")
        return False

    output_path = DATA_RAW / "player_counts.csv"
    df.to_csv(output_path, index=False)
    logger.info(f"Saved {len(df)} rows to {output_path}")

    # Print summary
    print("\nData Summary:")
    print(df.groupby("game").agg({
        "date": ["min", "max", "count"],
        "avg_players": ["mean", "max"]
    }))

    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
