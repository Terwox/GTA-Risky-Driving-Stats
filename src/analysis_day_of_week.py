"""
Chunk 9a: Day-of-Week Analysis.

Compares day-of-week patterns in treatment vs. reference periods.
Focuses on weekend-to-Monday transitions (gaming binges might show up here).
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import DATA_ANALYSIS, OUTPUT_FIGURES, OUTPUT_TABLES, setup_logging, ensure_dirs

logger = setup_logging(__name__)

DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


def load_tagged_data():
    """Load the tagged analysis dataset."""
    path = DATA_ANALYSIS / "tagged_violations.csv"
    if not path.exists():
        logger.error(f"Tagged data not found at {path}")
        return None

    df = pd.read_csv(path)
    df['date'] = pd.to_datetime(df['date'])
    logger.info(f"Loaded {len(df):,} tagged records")
    return df


def analyze_day_of_week(df: pd.DataFrame) -> pd.DataFrame:
    """Analyze day-of-week patterns by treatment and period."""
    # Ensure day_of_week is numeric
    df['day_of_week'] = pd.to_numeric(df['day_of_week'], errors='coerce')
    df = df.dropna(subset=['day_of_week'])
    df['day_of_week'] = df['day_of_week'].astype(int)

    # Aggregate by treatment, period, and day of week
    dow_stats = df.groupby(['treatment', 'period', 'day_of_week']).agg({
        'count': ['sum', 'mean', 'std']
    }).reset_index()

    dow_stats.columns = ['treatment', 'period', 'day_of_week', 'total', 'mean', 'std']
    dow_stats['day_name'] = dow_stats['day_of_week'].apply(lambda x: DAY_NAMES[int(x)])

    # Calculate percentage of weekly total
    weekly_totals = dow_stats.groupby(['treatment', 'period'])['total'].transform('sum')
    dow_stats['pct_of_week'] = dow_stats['total'] / weekly_totals * 100

    return dow_stats


def plot_day_of_week_comparison(dow_stats: pd.DataFrame, output_path: Path):
    """Plot day-of-week patterns comparing pre and post periods."""
    # Focus on GTA vs reference comparison
    treatments = ['gta', 'reference']
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    for idx, treatment in enumerate(treatments):
        ax = axes[idx]
        data = dow_stats[dow_stats['treatment'] == treatment]

        x = np.arange(7)
        width = 0.35

        pre_data = data[data['period'] == 'pre'].sort_values('day_of_week')
        post_data = data[data['period'] == 'post'].sort_values('day_of_week')

        if not pre_data.empty and not post_data.empty:
            ax.bar(x - width/2, pre_data['pct_of_week'], width, label='Pre', color='blue', alpha=0.7)
            ax.bar(x + width/2, post_data['pct_of_week'], width, label='Post', color='red', alpha=0.7)

        ax.set_xlabel('Day of Week')
        ax.set_ylabel('% of Weekly Violations')
        ax.set_title(f'{treatment.upper()} - Day of Week Distribution')
        ax.set_xticks(x)
        ax.set_xticklabels(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    logger.info(f"Saved day-of-week plot to {output_path}")


def analyze_weekend_effect(dow_stats: pd.DataFrame) -> pd.DataFrame:
    """Analyze weekend vs weekday patterns."""
    results = []

    for treatment in dow_stats['treatment'].unique():
        for period in ['pre', 'post']:
            data = dow_stats[(dow_stats['treatment'] == treatment) &
                            (dow_stats['period'] == period)]

            # Weekend: Fri-Sun (4, 5, 6)
            weekend = data[data['day_of_week'].isin([4, 5, 6])]['total'].sum()

            # Monday after weekend
            monday = data[data['day_of_week'] == 0]['total'].sum()

            # Rest of weekdays (Tue-Thu)
            midweek = data[data['day_of_week'].isin([1, 2, 3])]['total'].sum()

            total = data['total'].sum()

            results.append({
                'treatment': treatment,
                'period': period,
                'weekend_fri_sun': weekend,
                'monday': monday,
                'midweek_tue_thu': midweek,
                'total': total,
                'weekend_pct': weekend / total * 100 if total > 0 else 0,
                'monday_pct': monday / total * 100 if total > 0 else 0,
                'midweek_pct': midweek / total * 100 if total > 0 else 0,
            })

    return pd.DataFrame(results)


def main():
    """Main entry point for day-of-week analysis."""
    ensure_dirs()

    # Load data
    df = load_tagged_data()
    if df is None:
        return False

    # Analyze day of week patterns
    dow_stats = analyze_day_of_week(df)

    # Save stats
    dow_stats.to_csv(OUTPUT_TABLES / "day_of_week_stats.csv", index=False)

    # Plot comparison
    plot_day_of_week_comparison(dow_stats, OUTPUT_FIGURES / "day_of_week_comparison.png")

    # Weekend effect analysis
    weekend_effect = analyze_weekend_effect(dow_stats)
    weekend_effect.to_csv(OUTPUT_TABLES / "weekend_effect.csv", index=False)

    # Print summary
    print("\n=== Day-of-Week Analysis Summary ===")
    print("\nGTA Release - Weekend vs Weekday Patterns:")

    gta_pre = weekend_effect[(weekend_effect['treatment'] == 'gta') &
                              (weekend_effect['period'] == 'pre')].iloc[0]
    gta_post = weekend_effect[(weekend_effect['treatment'] == 'gta') &
                               (weekend_effect['period'] == 'post')].iloc[0]

    print(f"\nPre-release:")
    print(f"  Weekend (Fri-Sun): {gta_pre['weekend_pct']:.1f}%")
    print(f"  Monday:            {gta_pre['monday_pct']:.1f}%")
    print(f"  Midweek (Tue-Thu): {gta_pre['midweek_pct']:.1f}%")

    print(f"\nPost-release:")
    print(f"  Weekend (Fri-Sun): {gta_post['weekend_pct']:.1f}%")
    print(f"  Monday:            {gta_post['monday_pct']:.1f}%")
    print(f"  Midweek (Tue-Thu): {gta_post['midweek_pct']:.1f}%")

    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
