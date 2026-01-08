"""
Chunk 5: Process and standardize violation data from NYC and Chicago.

Standardizes schema to: city, date, hour, day_of_week, violation_type, count
Creates daily and hourly aggregates.
"""

import pandas as pd
import numpy as np
from pathlib import Path

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import DATA_RAW, DATA_PROCESSED, setup_logging, ensure_dirs

logger = setup_logging(__name__)


def process_nyc_violations() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Process NYC camera violations into daily and hourly aggregates.

    NYC data has individual violation records with:
    - issue_date: date of violation
    - violation_time: time like "10:46P" or "12:03A"
    - violation: type (e.g., "FAILURE TO STOP AT RED LIGHT")

    Returns:
        Tuple of (daily_df, hourly_df)
    """
    path = DATA_RAW / "nyc_camera_violations.csv"
    if not path.exists():
        logger.warning(f"NYC data not found at {path}")
        return pd.DataFrame(), pd.DataFrame()

    logger.info(f"Loading NYC violations from {path}...")

    # Load in chunks due to size
    chunks = []
    for chunk in pd.read_csv(path, chunksize=500000):
        chunks.append(chunk)
    df = pd.concat(chunks, ignore_index=True)

    logger.info(f"Loaded {len(df):,} NYC violation records")

    # Parse issue_date
    df['date'] = pd.to_datetime(df['issue_date'], format='%m/%d/%Y', errors='coerce')

    # Drop rows with invalid dates
    valid_dates = df['date'].notna()
    logger.info(f"Dropping {(~valid_dates).sum():,} rows with invalid dates")
    df = df[valid_dates].copy()

    # Filter to reasonable date range (2010-2025)
    reasonable_dates = (df['date'] >= '2010-01-01') & (df['date'] <= '2025-12-31')
    logger.info(f"Dropping {(~reasonable_dates).sum():,} rows outside 2010-2025 range")
    df = df[reasonable_dates].copy()

    # Parse violation time to extract hour
    def parse_time_to_hour(time_str):
        """Parse NYC time format like '10:46P' or '12:03A' to hour (0-23)."""
        if pd.isna(time_str) or not isinstance(time_str, str):
            return np.nan
        try:
            time_str = time_str.strip().upper()
            # Handle formats like "10:46P" or "10:46PM"
            is_pm = 'P' in time_str
            is_am = 'A' in time_str

            # Remove AM/PM indicator
            time_str = time_str.replace('PM', '').replace('AM', '').replace('P', '').replace('A', '')

            # Parse hour
            parts = time_str.split(':')
            hour = int(parts[0])

            # Convert to 24-hour format
            if is_pm and hour != 12:
                hour += 12
            elif is_am and hour == 12:
                hour = 0

            return hour
        except (ValueError, IndexError):
            return np.nan

    logger.info("Parsing violation times...")
    df['hour'] = df['violation_time'].apply(parse_time_to_hour)

    # Extract day of week (0=Monday, 6=Sunday)
    df['day_of_week'] = df['date'].dt.dayofweek

    # Classify violation type
    def classify_violation(v):
        if pd.isna(v):
            return 'unknown'
        v_upper = str(v).upper()
        if 'RED LIGHT' in v_upper:
            return 'redlight'
        elif 'SPEED' in v_upper or 'SCHOOL ZONE' in v_upper or 'CAMERA' in v_upper:
            return 'speed'
        else:
            return 'other'

    df['violation_type'] = df['violation'].apply(classify_violation)

    # Log violation type breakdown
    logger.info(f"Violation types: {df['violation_type'].value_counts().to_dict()}")

    # Create daily aggregates
    logger.info("Creating daily aggregates...")
    daily = df.groupby(['date', 'day_of_week', 'violation_type']).size().reset_index(name='count')
    daily['city'] = 'NYC'

    # Create hourly aggregates (only for rows with valid hours)
    logger.info("Creating hourly aggregates...")
    df_with_hour = df[df['hour'].notna()].copy()
    hourly = df_with_hour.groupby(['date', 'hour', 'day_of_week', 'violation_type']).size().reset_index(name='count')
    hourly['city'] = 'NYC'

    logger.info(f"NYC: {len(daily):,} daily records, {len(hourly):,} hourly records")

    return daily, hourly


def process_chicago_speed() -> pd.DataFrame:
    """
    Process Chicago speed camera violations.

    Chicago data is already aggregated by camera per day:
    - violation_date: date of violations
    - violations: count of violations
    - camera_id: camera identifier
    """
    path = DATA_RAW / "chicago_speed_violations.csv"
    if not path.exists():
        logger.warning(f"Chicago speed data not found at {path}")
        return pd.DataFrame()

    logger.info(f"Loading Chicago speed violations from {path}...")
    df = pd.read_csv(path)
    logger.info(f"Loaded {len(df):,} Chicago speed records")

    # Parse date
    df['date'] = pd.to_datetime(df['violation_date'], errors='coerce')

    # Drop rows with invalid dates
    valid_dates = df['date'].notna()
    df = df[valid_dates].copy()

    # Extract day of week
    df['day_of_week'] = df['date'].dt.dayofweek

    # Aggregate by date (sum all cameras for that day)
    daily = df.groupby(['date', 'day_of_week']).agg({
        'violations': 'sum'
    }).reset_index()

    daily = daily.rename(columns={'violations': 'count'})
    daily['city'] = 'Chicago'
    daily['violation_type'] = 'speed'

    logger.info(f"Chicago speed: {len(daily):,} daily records")
    return daily


def process_chicago_redlight() -> pd.DataFrame:
    """
    Process Chicago red light camera violations.

    Same structure as speed data.
    """
    path = DATA_RAW / "chicago_redlight_violations.csv"
    if not path.exists():
        logger.warning(f"Chicago red light data not found at {path}")
        return pd.DataFrame()

    logger.info(f"Loading Chicago red light violations from {path}...")
    df = pd.read_csv(path)
    logger.info(f"Loaded {len(df):,} Chicago red light records")

    # Parse date
    df['date'] = pd.to_datetime(df['violation_date'], errors='coerce')

    # Drop rows with invalid dates
    valid_dates = df['date'].notna()
    df = df[valid_dates].copy()

    # Extract day of week
    df['day_of_week'] = df['date'].dt.dayofweek

    # Aggregate by date (sum all cameras for that day)
    daily = df.groupby(['date', 'day_of_week']).agg({
        'violations': 'sum'
    }).reset_index()

    daily = daily.rename(columns={'violations': 'count'})
    daily['city'] = 'Chicago'
    daily['violation_type'] = 'redlight'

    logger.info(f"Chicago red light: {len(daily):,} daily records")
    return daily


def main():
    """Main entry point for violation data processing."""
    ensure_dirs()

    # Process NYC
    nyc_daily, nyc_hourly = process_nyc_violations()

    # Process Chicago
    chicago_speed = process_chicago_speed()
    chicago_redlight = process_chicago_redlight()

    # Combine daily data
    daily_dfs = [df for df in [nyc_daily, chicago_speed, chicago_redlight] if not df.empty]
    if not daily_dfs:
        logger.error("No daily violation data processed!")
        return False

    daily = pd.concat(daily_dfs, ignore_index=True)

    # Ensure consistent column order
    daily = daily[['city', 'date', 'day_of_week', 'violation_type', 'count']]
    daily = daily.sort_values(['city', 'date', 'violation_type']).reset_index(drop=True)

    # Save daily data
    daily_path = DATA_PROCESSED / "daily_violations.csv"
    daily.to_csv(daily_path, index=False)
    logger.info(f"Saved {len(daily):,} daily violation records to {daily_path}")

    # Save hourly data if available
    if not nyc_hourly.empty:
        hourly = nyc_hourly[['city', 'date', 'hour', 'day_of_week', 'violation_type', 'count']]
        hourly = hourly.sort_values(['city', 'date', 'hour', 'violation_type']).reset_index(drop=True)

        hourly_path = DATA_PROCESSED / "hourly_violations.csv"
        hourly.to_csv(hourly_path, index=False)
        logger.info(f"Saved {len(hourly):,} hourly violation records to {hourly_path}")
    else:
        logger.warning("No hourly data available")

    # Print summary
    print("\n=== Violation Data Processing Summary ===")
    print(f"\nDaily violations by city and type:")
    print(daily.groupby(['city', 'violation_type'])['count'].agg(['sum', 'count']).to_string())

    print(f"\nDate range:")
    for city in daily['city'].unique():
        city_data = daily[daily['city'] == city]
        print(f"  {city}: {city_data['date'].min().strftime('%Y-%m-%d')} to {city_data['date'].max().strftime('%Y-%m-%d')}")

    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
