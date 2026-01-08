"""
Chunk 2: Collect traffic camera violation data from NYC Open Data.

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

# NYC Open Data domain
NYC_DOMAIN = "data.cityofnewyork.us"

# Dataset IDs
# NYC combines camera violations into one dataset
NYC_CAMERA_VIOLATIONS_ID = "nc67-uf89"  # Open Parking and Camera Violations


def fetch_socrata_data(domain: str, dataset_id: str, limit_per_page: int = 50000) -> pd.DataFrame:
    """
    Fetch all data from a Socrata dataset using pagination.

    Args:
        domain: Socrata domain (e.g., "data.cityofnewyork.us")
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


def collect_nyc_camera_violations() -> pd.DataFrame:
    """
    Collect NYC camera violations (red light and speed combined).

    The NYC Open Parking and Camera Violations dataset contains both types.
    We'll filter for camera-related violations only.
    """
    logger.info("Collecting NYC Camera Violations...")

    # For this large dataset, we'll use a query to filter camera violations
    # This is more efficient than downloading everything
    client = Socrata(NYC_DOMAIN, None)
    client.timeout = 120

    all_records = []
    offset = 0
    limit = 50000

    # Query for camera-related violations only
    # Camera violations typically have specific codes or types
    while True:
        logger.info(f"  Fetching records {offset} to {offset + limit}...")
        try:
            # Filter for camera violations by checking violation description
            records = client.get(
                NYC_CAMERA_VIOLATIONS_ID,
                limit=limit,
                offset=offset,
                where="violation LIKE '%CAMERA%' OR violation LIKE '%SPEED%PHOTO%' OR violation LIKE '%RED LIGHT%'"
            )
        except Exception as e:
            logger.error(f"  Error fetching data: {e}")
            # Try without filter if the query fails
            try:
                logger.info("  Trying without filter...")
                records = client.get(
                    NYC_CAMERA_VIOLATIONS_ID,
                    limit=limit,
                    offset=offset
                )
            except Exception as e2:
                logger.error(f"  Error fetching data without filter: {e2}")
                break

        if not records:
            break

        all_records.extend(records)
        offset += limit
        time.sleep(0.5)

        # Safety limit
        if len(all_records) >= 5_000_000:
            logger.warning("  Hit 5M record limit")
            break

    client.close()

    df = pd.DataFrame.from_records(all_records)
    logger.info(f"  Fetched {len(df):,} total records")

    if not df.empty:
        logger.info(f"  Columns: {df.columns.tolist()}")

    return df


def main():
    """Main entry point for NYC violation data collection."""
    ensure_dirs()

    # Collect camera violations (combined dataset)
    camera_df = collect_nyc_camera_violations()

    if not camera_df.empty:
        # Save all camera violations
        output_path = DATA_RAW / "nyc_camera_violations.csv"
        camera_df.to_csv(output_path, index=False)
        logger.info(f"Saved {len(camera_df):,} camera violations to {output_path}")

        # Print summary
        print("\n=== NYC Data Collection Summary ===")
        print(f"Camera Violations: {len(camera_df):,} records")
        print(f"  Columns: {camera_df.columns.tolist()}")

        # Show violation type breakdown if available
        if 'violation' in camera_df.columns:
            print("\n  Violation types (top 10):")
            print(camera_df['violation'].value_counts().head(10))

        return True
    else:
        logger.error("No camera violation data collected")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
