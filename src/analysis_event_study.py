"""
Chunk 9b: Event Study Analysis.

Creates event study visualization centering violations on release date (day 0).
Shows daily violations from day -30 to day +90 relative to release.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import (
    DATA_PROCESSED, OUTPUT_FIGURES, GAME_RELEASES,
    setup_logging, ensure_dirs
)

logger = setup_logging(__name__)


def load_daily_violations():
    """Load daily violation data."""
    path = DATA_PROCESSED / "daily_violations.csv"
    if not path.exists():
        logger.error(f"Daily violations not found at {path}")
        return None

    df = pd.read_csv(path)
    df['date'] = pd.to_datetime(df['date'])
    logger.info(f"Loaded {len(df):,} daily violation records")
    return df


def create_event_study_data(daily: pd.DataFrame, game: str, release_date: pd.Timestamp,
                            days_before: int = 30, days_after: int = 90) -> pd.DataFrame:
    """
    Create event study data centered on release date.

    Args:
        daily: Daily violation data
        game: Game name for labeling
        release_date: Release date to center on
        days_before: Days before release to include
        days_after: Days after release to include

    Returns:
        DataFrame with days_from_release and violation counts
    """
    start_date = release_date - pd.Timedelta(days=days_before)
    end_date = release_date + pd.Timedelta(days=days_after)

    # Filter to event window
    event_data = daily[(daily['date'] >= start_date) & (daily['date'] <= end_date)].copy()

    if event_data.empty:
        logger.warning(f"No data for {game} event window")
        return pd.DataFrame()

    # Calculate days from release
    event_data['days_from_release'] = (event_data['date'] - release_date).dt.days

    # Aggregate by day (across cities and violation types)
    event_agg = event_data.groupby('days_from_release').agg({
        'count': 'sum',
        'date': 'first'
    }).reset_index()

    event_agg['game'] = game
    event_agg['release_date'] = release_date

    return event_agg


def plot_event_study(event_data: pd.DataFrame, game: str,
                     lag_days: int, output_path: Path):
    """
    Plot event study for a single game.

    Args:
        event_data: Event study data
        game: Game name
        lag_days: Days of lag before analysis window starts
        output_path: Where to save plot
    """
    fig, ax = plt.subplots(figsize=(14, 6))

    x = event_data['days_from_release']
    y = event_data['count']

    # Plot line
    ax.plot(x, y, 'b-', linewidth=1.5, alpha=0.8)
    ax.fill_between(x, 0, y, alpha=0.3)

    # Add 7-day rolling average
    event_data_sorted = event_data.sort_values('days_from_release')
    rolling_avg = event_data_sorted['count'].rolling(window=7, center=True).mean()
    ax.plot(event_data_sorted['days_from_release'], rolling_avg, 'r-',
            linewidth=2, label='7-day moving average')

    # Mark key dates
    ax.axvline(x=0, color='green', linestyle='--', linewidth=2, label='Release Date (Day 0)')
    ax.axvline(x=lag_days, color='orange', linestyle='--', linewidth=2,
               label=f'Stabilization (Day {lag_days})')
    ax.axvline(x=lag_days + 28, color='red', linestyle='--', linewidth=2,
               label=f'Analysis Window End (Day {lag_days + 28})')

    # Shade analysis window
    ax.axvspan(lag_days, lag_days + 28, alpha=0.1, color='yellow', label='Analysis Window')

    # Shade pre-period
    ax.axvspan(-42, -14, alpha=0.1, color='blue', label='Pre-period (-42 to -14)')

    ax.set_xlabel('Days from Release', fontsize=12)
    ax.set_ylabel('Daily Violations (All Cities)', fontsize=12)
    ax.set_title(f'Event Study: {game} Release', fontsize=14)
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)

    # Format y-axis
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: format(int(x), ',')))

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    logger.info(f"Saved event study plot for {game} to {output_path}")


def plot_combined_event_study(all_events: pd.DataFrame, output_path: Path):
    """Plot all games on one event study chart."""
    fig, ax = plt.subplots(figsize=(14, 8))

    games = all_events['game'].unique()
    colors = {'GTA V': 'red', 'Elden Ring': 'blue', 'Halo Infinite': 'green', 'Fallout 4': 'purple'}

    for game in games:
        game_data = all_events[all_events['game'] == game].sort_values('days_from_release')

        # Normalize to pre-period mean for comparison
        pre_mean = game_data[game_data['days_from_release'].between(-42, -14)]['count'].mean()
        if pre_mean > 0:
            game_data['normalized'] = game_data['count'] / pre_mean * 100

            # 7-day rolling average
            rolling = game_data['normalized'].rolling(window=7, center=True).mean()

            color = colors.get(game, 'gray')
            ax.plot(game_data['days_from_release'], rolling,
                   linewidth=2, label=game, color=color)

    # Mark release date
    ax.axvline(x=0, color='black', linestyle='--', linewidth=2, alpha=0.5)
    ax.axhline(y=100, color='gray', linestyle=':', alpha=0.5, label='Pre-period baseline')

    ax.set_xlabel('Days from Release', fontsize=12)
    ax.set_ylabel('Violations (% of Pre-period Mean)', fontsize=12)
    ax.set_title('Event Study: Game Releases and Traffic Violations', fontsize=14)
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    logger.info(f"Saved combined event study to {output_path}")


def main():
    """Main entry point for event study analysis."""
    ensure_dirs()

    # Load data
    daily = load_daily_violations()
    if daily is None:
        return False

    all_events = []

    # Create event study for each game
    for game, info in GAME_RELEASES.items():
        release_str = info.get('pc') or info.get('console')
        if not release_str:
            continue

        release_date = pd.to_datetime(release_str)

        # Check if we have data around this date
        check_start = release_date - pd.Timedelta(days=30)
        check_end = release_date + pd.Timedelta(days=30)
        has_data = ((daily['date'] >= check_start) & (daily['date'] <= check_end)).any()

        if not has_data:
            logger.warning(f"No data around {game} release ({release_date})")
            continue

        # Create event study data
        event_data = create_event_study_data(daily, game, release_date)

        if event_data.empty:
            continue

        all_events.append(event_data)

        # Plot individual event study
        lag_days = 60  # From chunk 4 analysis
        plot_path = OUTPUT_FIGURES / f"event_study_{game.lower().replace(' ', '_')}.png"
        plot_event_study(event_data, game, lag_days, plot_path)

    if not all_events:
        logger.error("No event study data generated!")
        return False

    # Combine all events
    combined = pd.concat(all_events, ignore_index=True)
    combined.to_csv(DATA_PROCESSED / "event_study_data.csv", index=False)

    # Plot combined event study
    plot_combined_event_study(combined, OUTPUT_FIGURES / "event_study_combined.png")

    print("\n=== Event Study Summary ===")
    print(f"Created event studies for {len(all_events)} games")
    for e in all_events:
        game = e['game'].iloc[0]
        n_days = len(e)
        print(f"  {game}: {n_days} days of data")

    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
