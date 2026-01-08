"""
Chunk 8: Time-of-Day Analysis.

Analyzes hourly patterns in violations, comparing pre and post periods
to see if GTA releases shift when violations occur (e.g., more evening
violations when people are playing/influenced by the game).
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import (
    DATA_PROCESSED, DATA_ANALYSIS, OUTPUT_FIGURES, OUTPUT_TABLES,
    GAME_RELEASES, setup_logging, ensure_dirs
)

logger = setup_logging(__name__)


def load_hourly_data():
    """Load hourly violation data if available."""
    path = DATA_PROCESSED / "hourly_violations.csv"
    if not path.exists():
        logger.warning(f"Hourly data not found at {path}")
        return None

    df = pd.read_csv(path)
    df['date'] = pd.to_datetime(df['date'])
    logger.info(f"Loaded {len(df):,} hourly violation records")

    return df


def tag_hourly_data(hourly: pd.DataFrame) -> pd.DataFrame:
    """Tag hourly data with release periods (similar to daily tagging)."""
    # Get GTA V release date
    gta_info = GAME_RELEASES.get('GTA V', {})
    release_str = gta_info.get('pc') or gta_info.get('console')
    if not release_str:
        logger.error("GTA V release date not found")
        return pd.DataFrame()

    release_date = pd.to_datetime(release_str)
    lag_days = 60  # Use 60 days lag as determined in chunk 4

    # Define periods
    pre_start = release_date - pd.Timedelta(days=42)
    pre_end = release_date - pd.Timedelta(days=14)
    post_start = release_date + pd.Timedelta(days=lag_days)
    post_end = post_start + pd.Timedelta(days=28)

    # Tag data
    pre_mask = (hourly['date'] >= pre_start) & (hourly['date'] <= pre_end)
    post_mask = (hourly['date'] >= post_start) & (hourly['date'] <= post_end)

    pre_data = hourly[pre_mask].copy()
    pre_data['period'] = 'pre'

    post_data = hourly[post_mask].copy()
    post_data['period'] = 'post'

    tagged = pd.concat([pre_data, post_data], ignore_index=True)
    logger.info(f"Tagged {len(tagged):,} hourly records (pre: {len(pre_data)}, post: {len(post_data)})")

    return tagged


def analyze_hourly_distribution(tagged: pd.DataFrame) -> pd.DataFrame:
    """Analyze hourly distribution of violations by period."""
    # Ensure hour is numeric
    tagged['hour'] = pd.to_numeric(tagged['hour'], errors='coerce')
    tagged = tagged.dropna(subset=['hour'])
    tagged['hour'] = tagged['hour'].astype(int)

    # Aggregate by period and hour
    hourly_dist = tagged.groupby(['period', 'hour']).agg({
        'count': 'sum'
    }).reset_index()

    # Calculate percentage of daily total for each period
    period_totals = hourly_dist.groupby('period')['count'].transform('sum')
    hourly_dist['pct_of_total'] = hourly_dist['count'] / period_totals * 100

    return hourly_dist


def plot_hourly_distribution(hourly_dist: pd.DataFrame, output_path: Path):
    """Plot hourly distribution comparison between pre and post periods."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Plot 1: Absolute counts
    ax1 = axes[0]
    for period in ['pre', 'post']:
        data = hourly_dist[hourly_dist['period'] == period].sort_values('hour')
        color = 'blue' if period == 'pre' else 'red'
        ax1.plot(data['hour'], data['count'], marker='o', label=period.capitalize(),
                color=color, linewidth=2, markersize=4)

    ax1.set_xlabel('Hour of Day')
    ax1.set_ylabel('Total Violations')
    ax1.set_title('Hourly Violation Distribution (Absolute)')
    ax1.legend()
    ax1.set_xticks(range(0, 24, 2))
    ax1.grid(True, alpha=0.3)

    # Shade evening hours (7pm-10pm)
    ax1.axvspan(19, 22, alpha=0.2, color='yellow', label='Evening peak')

    # Plot 2: Percentage of daily total
    ax2 = axes[1]
    for period in ['pre', 'post']:
        data = hourly_dist[hourly_dist['period'] == period].sort_values('hour')
        color = 'blue' if period == 'pre' else 'red'
        ax2.plot(data['hour'], data['pct_of_total'], marker='o', label=period.capitalize(),
                color=color, linewidth=2, markersize=4)

    ax2.set_xlabel('Hour of Day')
    ax2.set_ylabel('% of Daily Violations')
    ax2.set_title('Hourly Violation Distribution (Percentage)')
    ax2.legend()
    ax2.set_xticks(range(0, 24, 2))
    ax2.grid(True, alpha=0.3)

    # Shade evening hours
    ax2.axvspan(19, 22, alpha=0.2, color='yellow')

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    logger.info(f"Saved hourly distribution plot to {output_path}")


def analyze_peak_hours(hourly_dist: pd.DataFrame) -> pd.DataFrame:
    """Analyze changes in peak hours between periods."""
    results = []

    for period in ['pre', 'post']:
        data = hourly_dist[hourly_dist['period'] == period]

        # Morning peak (7-9am)
        morning = data[data['hour'].between(7, 9)]['count'].sum()

        # Afternoon peak (12-2pm)
        afternoon = data[data['hour'].between(12, 14)]['count'].sum()

        # Evening peak (7-10pm)
        evening = data[data['hour'].between(19, 22)]['count'].sum()

        # Late night (10pm-2am)
        late_night = data[(data['hour'] >= 22) | (data['hour'] <= 2)]['count'].sum()

        total = data['count'].sum()

        results.append({
            'period': period,
            'morning_7_9': morning,
            'afternoon_12_14': afternoon,
            'evening_19_22': evening,
            'late_night_22_2': late_night,
            'total': total,
            'morning_pct': morning / total * 100 if total > 0 else 0,
            'afternoon_pct': afternoon / total * 100 if total > 0 else 0,
            'evening_pct': evening / total * 100 if total > 0 else 0,
            'late_night_pct': late_night / total * 100 if total > 0 else 0,
        })

    return pd.DataFrame(results)


def main():
    """Main entry point for time-of-day analysis."""
    ensure_dirs()

    # Load hourly data
    hourly = load_hourly_data()

    if hourly is None:
        print("CHUNK 8 SKIPPED: No hourly data available")
        return True  # Not a failure, just conditional skip

    # Tag with release periods
    tagged = tag_hourly_data(hourly)

    if tagged.empty:
        logger.error("No tagged hourly data!")
        return False

    # Analyze distribution
    hourly_dist = analyze_hourly_distribution(tagged)

    # Plot distribution
    plot_hourly_distribution(hourly_dist, OUTPUT_FIGURES / "hourly_distribution.png")

    # Analyze peak hours
    peak_analysis = analyze_peak_hours(hourly_dist)
    peak_analysis.to_csv(OUTPUT_TABLES / "hourly_peak_analysis.csv", index=False)

    # Print summary
    print("\n=== Time-of-Day Analysis Summary ===")
    print("\nPeak Hour Analysis (GTA V Release):")
    print(peak_analysis.to_string(index=False))

    # Calculate changes
    pre = peak_analysis[peak_analysis['period'] == 'pre'].iloc[0]
    post = peak_analysis[peak_analysis['period'] == 'post'].iloc[0]

    print("\nChanges from Pre to Post:")
    print(f"  Morning (7-9am):    {pre['morning_pct']:.1f}% -> {post['morning_pct']:.1f}%")
    print(f"  Afternoon (12-2pm): {pre['afternoon_pct']:.1f}% -> {post['afternoon_pct']:.1f}%")
    print(f"  Evening (7-10pm):   {pre['evening_pct']:.1f}% -> {post['evening_pct']:.1f}%")
    print(f"  Late Night (10p-2a):{pre['late_night_pct']:.1f}% -> {post['late_night_pct']:.1f}%")

    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
