"""
Chunk 6: Create analysis dataset with tagged periods.

Tags violations with treatment windows, periods, and release identifiers
for the difference-in-differences analysis.
"""

import pandas as pd
import numpy as np
from pathlib import Path

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import DATA_PROCESSED, DATA_ANALYSIS, setup_logging, ensure_dirs

logger = setup_logging(__name__)


def load_data():
    """Load processed violation and release window data."""
    # Load daily violations
    daily_path = DATA_PROCESSED / "daily_violations.csv"
    if not daily_path.exists():
        logger.error(f"Daily violations not found at {daily_path}")
        return None, None

    daily = pd.read_csv(daily_path)
    daily['date'] = pd.to_datetime(daily['date'])
    logger.info(f"Loaded {len(daily):,} daily violation records")

    # Load release windows
    release_path = DATA_PROCESSED / "release_windows.csv"
    if not release_path.exists():
        logger.error(f"Release windows not found at {release_path}")
        return None, None

    releases = pd.read_csv(release_path)
    for col in ['release_date', 'peak_date', 'stabilization_date']:
        releases[col] = pd.to_datetime(releases[col])
    logger.info(f"Loaded {len(releases)} game releases")

    return daily, releases


def tag_violations(daily: pd.DataFrame, releases: pd.DataFrame) -> pd.DataFrame:
    """
    Tag each violation record with treatment information.

    For each release, we define:
    - Pre-period: [release_date - 42 days, release_date - 14 days]
    - Post-period: [stabilization_date, stabilization_date + 28 days]
      OR using recommended lag: [release_date + lag, release_date + lag + 28 days]

    Treatment types:
    - 'gta': GTA V release
    - 'comparison': Other game releases (placebo)
    - 'reference': Same calendar dates in a different year (control)
    """
    all_tagged = []

    for _, release in releases.iterrows():
        game = release['game']
        release_date = release['release_date']
        lag_days = release['recommended_lag_days']

        # Define analysis windows
        # Pre-period: 42 to 14 days before release
        pre_start = release_date - pd.Timedelta(days=42)
        pre_end = release_date - pd.Timedelta(days=14)

        # Post-period: starts after lag (when players stabilize), lasts 28 days
        post_start = release_date + pd.Timedelta(days=lag_days)
        post_end = post_start + pd.Timedelta(days=28)

        logger.info(f"{game}: Pre [{pre_start.date()} to {pre_end.date()}], "
                    f"Post [{post_start.date()} to {post_end.date()}]")

        # Determine treatment type
        if 'gta' in game.lower():
            treatment = 'gta'
        else:
            treatment = 'comparison'

        # Tag violations in pre-period
        pre_mask = (daily['date'] >= pre_start) & (daily['date'] <= pre_end)
        pre_violations = daily[pre_mask].copy()
        pre_violations['period'] = 'pre'
        pre_violations['treatment'] = treatment
        pre_violations['release_id'] = game
        pre_violations['release_date'] = release_date
        pre_violations['days_from_release'] = (pre_violations['date'] - release_date).dt.days

        # Tag violations in post-period
        post_mask = (daily['date'] >= post_start) & (daily['date'] <= post_end)
        post_violations = daily[post_mask].copy()
        post_violations['period'] = 'post'
        post_violations['treatment'] = treatment
        post_violations['release_id'] = game
        post_violations['release_date'] = release_date
        post_violations['days_from_release'] = (post_violations['date'] - release_date).dt.days

        all_tagged.append(pre_violations)
        all_tagged.append(post_violations)

        # Create reference year windows (same dates, different year)
        # Use 1 year before or after the release
        for year_offset in [-1, 1]:
            try:
                ref_pre_start = pre_start + pd.DateOffset(years=year_offset)
                ref_pre_end = pre_end + pd.DateOffset(years=year_offset)
                ref_post_start = post_start + pd.DateOffset(years=year_offset)
                ref_post_end = post_end + pd.DateOffset(years=year_offset)

                # Reference pre-period
                ref_pre_mask = (daily['date'] >= ref_pre_start) & (daily['date'] <= ref_pre_end)
                ref_pre = daily[ref_pre_mask].copy()
                if not ref_pre.empty:
                    ref_pre['period'] = 'pre'
                    ref_pre['treatment'] = 'reference'
                    ref_pre['release_id'] = f"{game}_ref_{year_offset:+d}yr"
                    ref_pre['release_date'] = release_date + pd.DateOffset(years=year_offset)
                    ref_pre['days_from_release'] = (
                        ref_pre['date'] - ref_pre['release_date']
                    ).dt.days
                    all_tagged.append(ref_pre)

                # Reference post-period
                ref_post_mask = (daily['date'] >= ref_post_start) & (daily['date'] <= ref_post_end)
                ref_post = daily[ref_post_mask].copy()
                if not ref_post.empty:
                    ref_post['period'] = 'post'
                    ref_post['treatment'] = 'reference'
                    ref_post['release_id'] = f"{game}_ref_{year_offset:+d}yr"
                    ref_post['release_date'] = release_date + pd.DateOffset(years=year_offset)
                    ref_post['days_from_release'] = (
                        ref_post['date'] - ref_post['release_date']
                    ).dt.days
                    all_tagged.append(ref_post)

            except Exception as e:
                logger.warning(f"Could not create reference year {year_offset} for {game}: {e}")

    if not all_tagged:
        logger.error("No violations tagged!")
        return pd.DataFrame()

    tagged = pd.concat(all_tagged, ignore_index=True)

    # Convert release_date back to string for CSV storage
    tagged['release_date'] = tagged['release_date'].dt.strftime('%Y-%m-%d')

    logger.info(f"Tagged {len(tagged):,} violation records")
    return tagged


def main():
    """Main entry point for analysis dataset creation."""
    ensure_dirs()

    # Load data
    daily, releases = load_data()
    if daily is None or releases is None:
        return False

    # Tag violations
    tagged = tag_violations(daily, releases)

    if tagged.empty:
        logger.error("No tagged violations!")
        return False

    # Save tagged dataset
    output_path = DATA_ANALYSIS / "tagged_violations.csv"
    tagged.to_csv(output_path, index=False)
    logger.info(f"Saved tagged violations to {output_path}")

    # Print summary
    print("\n=== Analysis Dataset Summary ===")
    print(f"\nTotal tagged records: {len(tagged):,}")

    print("\nBy treatment and period:")
    summary = tagged.groupby(['treatment', 'period'])['count'].agg(['sum', 'count'])
    print(summary.to_string())

    print("\nBy release:")
    release_summary = tagged.groupby(['release_id', 'treatment', 'period'])['count'].agg(['sum', 'count'])
    print(release_summary.to_string())

    print("\nDate coverage:")
    print(f"  Earliest: {tagged['date'].min()}")
    print(f"  Latest: {tagged['date'].max()}")

    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
