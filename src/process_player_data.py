"""
Chunk 4: Process player data and find stabilization dates.

Loads player count data, fits decay curves, identifies when games
stabilize after release (for analysis window definition).
"""

import pandas as pd
import numpy as np
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
from pathlib import Path

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import (
    DATA_RAW, DATA_PROCESSED, OUTPUT_FIGURES,
    GAME_RELEASES, setup_logging, ensure_dirs
)

logger = setup_logging(__name__)


def exponential_decay(x, a, b, c):
    """Exponential decay function: a * exp(-b * x) + c"""
    return a * np.exp(-b * x) + c


def find_stabilization_point(df: pd.DataFrame, game: str, release_date: pd.Timestamp) -> dict:
    """
    Analyze player data for a game and find when it stabilizes post-release.

    Stabilization is defined as when monthly player change drops below 15%
    after the initial release spike (within first 6 months).

    Args:
        df: Player data for this game
        game: Game name
        release_date: Known release date

    Returns:
        dict with release_date, peak_date, stabilization_date, recommended_lag_days
    """
    # Filter to post-release data
    # Use the start of the release month (not exact date) since we have monthly data
    release_month_start = release_date.replace(day=1)
    df = df[df['date'] >= release_month_start].copy()

    if df.empty:
        logger.warning(f"No post-release data for {game}")
        return None

    df = df.sort_values('date').reset_index(drop=True)

    # Find INITIAL peak (within first 6 months after release, not overall peak)
    # This captures the release-window behavior, not later DLC bumps
    initial_window = df[df['date'] <= release_date + pd.Timedelta(days=180)]

    if initial_window.empty:
        logger.warning(f"{game}: No data in initial 6-month window")
        return None

    peak_idx = initial_window['avg_players'].idxmax()
    peak_date = df.loc[peak_idx, 'date']
    peak_players = df.loc[peak_idx, 'avg_players']

    logger.info(f"{game}: Initial peak at {peak_date.strftime('%Y-%m')} with {peak_players:,} players")

    # Calculate month-over-month change for all post-release data
    df['prev_players'] = df['avg_players'].shift(1)
    df['pct_change'] = (df['avg_players'] - df['prev_players']) / df['prev_players'] * 100
    df['abs_pct_change'] = df['pct_change'].abs()

    # Filter to post-peak data (after initial peak)
    post_peak = df[df['date'] > peak_date].copy()

    if post_peak.empty:
        logger.warning(f"{game}: No data after peak")
        # Use peak date + 30 days as default
        return {
            'game': game,
            'release_date': release_date.strftime('%Y-%m-%d'),
            'peak_date': peak_date.strftime('%Y-%m-%d'),
            'stabilization_date': (peak_date + pd.Timedelta(days=30)).strftime('%Y-%m-%d'),
            'recommended_lag_days': 30,
            'peak_players': int(peak_players),
        }

    # Find stabilization: when monthly change drops below 15% consistently
    # Also require that player count has dropped to less than 30% of peak
    # (to avoid flagging early in the decay curve)
    threshold = 15.0  # 15% month-over-month change
    decay_threshold = 0.30  # Must be below 30% of peak to be "stable"

    post_peak['decay_ratio'] = post_peak['avg_players'] / peak_players

    # Look for first month where:
    # 1. Absolute change is below threshold
    # 2. Player count has dropped significantly from peak
    stabilized_rows = post_peak[
        (post_peak['abs_pct_change'] < threshold) &
        (post_peak['decay_ratio'] < decay_threshold)
    ]

    if not stabilized_rows.empty:
        stabilization_date = stabilized_rows.iloc[0]['date']
    else:
        # If no point meets both criteria, look for just the decay threshold
        decayed_rows = post_peak[post_peak['decay_ratio'] < decay_threshold]
        if not decayed_rows.empty:
            stabilization_date = decayed_rows.iloc[0]['date']
        else:
            # Default to 4 months post-release if still hasn't decayed
            stabilization_date = release_date + pd.Timedelta(days=120)

    # Calculate recommended lag (days from release to stabilization)
    lag_days = (stabilization_date - release_date).days

    # Clamp to reasonable range (14-60 days for analysis purposes)
    # The spec suggests using ~2-4 weeks of lag
    recommended_lag = min(max(lag_days, 14), 60)

    logger.info(f"{game}: Stabilized at {stabilization_date.strftime('%Y-%m')} "
                f"({lag_days} days from release, using {recommended_lag} day lag)")

    return {
        'game': game,
        'release_date': release_date.strftime('%Y-%m-%d'),
        'peak_date': peak_date.strftime('%Y-%m-%d'),
        'stabilization_date': stabilization_date.strftime('%Y-%m-%d'),
        'recommended_lag_days': recommended_lag,
        'peak_players': int(peak_players),
    }


def plot_player_curve(df: pd.DataFrame, game: str, release_date: pd.Timestamp,
                      stabilization_date: pd.Timestamp, output_path: Path):
    """Generate player engagement curve plot for a game."""
    plt.figure(figsize=(12, 6))

    # Plot all data
    plt.plot(df['date'], df['avg_players'], 'b-', linewidth=2, label='Avg Players')
    plt.fill_between(df['date'], 0, df['avg_players'], alpha=0.3)

    # Mark release date
    plt.axvline(x=release_date, color='green', linestyle='--',
                linewidth=2, label=f'Release ({release_date.strftime("%Y-%m-%d")})')

    # Mark stabilization date
    plt.axvline(x=stabilization_date, color='red', linestyle='--',
                linewidth=2, label=f'Stabilization ({stabilization_date.strftime("%Y-%m-%d")})')

    plt.xlabel('Date', fontsize=12)
    plt.ylabel('Average Players', fontsize=12)
    plt.title(f'{game} - Player Engagement Over Time', fontsize=14)
    plt.legend(loc='upper right')
    plt.grid(True, alpha=0.3)

    # Format y-axis with thousands separator
    plt.gca().yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, p: format(int(x), ','))
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    logger.info(f"Saved plot to {output_path}")


def process_all_games() -> pd.DataFrame:
    """
    Process player data for all games and generate release windows.

    Returns:
        DataFrame with release windows for each game
    """
    # Load player data
    player_path = DATA_RAW / "player_counts.csv"
    if not player_path.exists():
        logger.error(f"Player data not found at {player_path}")
        return pd.DataFrame()

    df = pd.read_csv(player_path)
    df['date'] = pd.to_datetime(df['date'])

    logger.info(f"Loaded {len(df):,} player data rows for {df['game'].nunique()} games")

    results = []

    for game, info in GAME_RELEASES.items():
        if game not in df['game'].values:
            logger.warning(f"No data for {game}")
            continue

        # Get release date (prefer PC release for Steam data)
        release_str = info.get('pc') or info.get('console')
        if not release_str:
            logger.warning(f"No release date for {game}")
            continue

        release_date = pd.to_datetime(release_str)

        # Get game data
        game_df = df[df['game'] == game].copy()

        # Find stabilization
        result = find_stabilization_point(game_df, game, release_date)
        if result:
            results.append(result)

            # Generate plot
            plot_path = OUTPUT_FIGURES / f"player_curve_{game.lower().replace(' ', '_')}.png"
            plot_player_curve(
                game_df, game, release_date,
                pd.to_datetime(result['stabilization_date']),
                plot_path
            )

    return pd.DataFrame(results)


def main():
    """Main entry point for player data processing."""
    ensure_dirs()

    logger.info("Processing player data...")
    release_windows = process_all_games()

    if release_windows.empty:
        logger.error("No release windows generated!")
        return False

    # Save release windows
    output_path = DATA_PROCESSED / "release_windows.csv"
    release_windows.to_csv(output_path, index=False)
    logger.info(f"Saved release windows to {output_path}")

    # Print summary
    print("\n=== Release Windows Summary ===")
    print(release_windows.to_string(index=False))

    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
