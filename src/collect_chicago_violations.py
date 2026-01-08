"""
Chunk 3: Collect traffic camera violation data from Chicago Data Portal.

Uses Socrata API to pull red light and speed camera violations.
"""

import time
import pandas as pd
from pathlib import Path
from sodapy import Socrata

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import DATA_RAW, setup_logging, ensure_dirs

logger = setup_logging(__name__)

# Chicago Data Portal domain
CHICAGO_DOMAIN = "data.cityofchicago.org"

# Dataset IDs
CHICAGO_SPEED_ID = "hhkd-xvj4"  # Speed Camera Violations
CHICAGO_REDLIGHT_ID = "spqx-js37"  # Red Light Camera Violations


def fetch_socrata_data(domain: str, dataset_id: str, limit_per_page: int = 50000) -> pd.DataFrame:
    """
    Fetch all data from a Socrata dataset using pagination.

    Args:
        domain: Socrata domain
        dataset_id: Dataset identifier
        limit_per_page: Number of records per API request

    Returns:
        DataFrame with all records
    """
    logger.info(f"Fetching data from {domain}/{dataset_id}")

    # Create client (no auth needed for public data, but rate limited)
    client = Socrata(domain, None)
    client.timeout = 60

    all_records = []
    offset = 0

    while True:
        logger.info(f"  Fetching records {offset} to {offset + limit_per_page}...")
        try:
            records = client.get(dataset_id, limit=limit_per_page, offset=offset)
        except Exception as e:
            logger.error(f"  Error fetching data: {e}")
            break

        if not records:
            break

        all_records.extend(records)
        offset += limit_per_page

        # Be nice to the API
        time.sleep(0.5)

        # Safety limit - some datasets have tens of millions of rows
        if len(all_records) >= 5_000_000:
            logger.warning("  Hit 5M record limit, stopping pagination")
            break

    client.close()

    df = pd.DataFrame.from_records(all_records)
    logger.info(f"  Fetched {len(df):,} total records")
    return df


def collect_chicago_speed() -> pd.DataFrame:
    """Collect Chicago speed camera violations."""
    logger.info("Collecting Chicago Speed Camera Violations...")
    df = fetch_socrata_data(CHICAGO_DOMAIN, CHICAGO_SPEED_ID)

    if df.empty:
        logger.warning("No speed data collected")
        return df

    # Log column info
    logger.info(f"  Columns: {df.columns.tolist()}")

    return df


def collect_chicago_redlight() -> pd.DataFrame:
    """Collect Chicago red light camera violations."""
    logger.info("Collecting Chicago Red Light Camera Violations...")
    df = fetch_socrata_data(CHICAGO_DOMAIN, CHICAGO_REDLIGHT_ID)

    if df.empty:
        logger.warning("No red light data collected")
        return df

    # Log column info
    logger.info(f"  Columns: {df.columns.tolist()}")

    return df


def main():
    """Main entry point for Chicago violation data collection."""
    ensure_dirs()

    # Collect speed violations
    speed_df = collect_chicago_speed()
    if not speed_df.empty:
        output_path = DATA_RAW / "chicago_speed_violations.csv"
        speed_df.to_csv(output_path, index=False)
        logger.info(f"Saved {len(speed_df):,} speed violations to {output_path}")

    # Collect red light violations
    redlight_df = collect_chicago_redlight()
    if not redlight_df.empty:
        output_path = DATA_RAW / "chicago_redlight_violations.csv"
        redlight_df.to_csv(output_path, index=False)
        logger.info(f"Saved {len(redlight_df):,} red light violations to {output_path}")

    # Print summary
    print("\n=== Chicago Data Collection Summary ===")
    if not speed_df.empty:
        print(f"Speed Violations: {len(speed_df):,} records")
        print(f"  Columns: {speed_df.columns.tolist()}")
    if not redlight_df.empty:
        print(f"Red Light Violations: {len(redlight_df):,} records")
        print(f"  Columns: {redlight_df.columns.tolist()}")

    return not (speed_df.empty and redlight_df.empty)


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
