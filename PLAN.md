# Implementation Plan: GTA Release and Traffic Violation Analysis

## Overview

This plan breaks the SPEC into 10 implementation chunks. Each chunk is self-contained, testable, and builds on the previous chunk. **No chunk proceeds until the previous chunk's validation passes.**

---

## Chunk 0: Project Setup
**Goal**: Set up directory structure, dependencies, and basic infrastructure.

### Tasks
1. Create directory structure (`data/raw`, `data/processed`, `data/analysis`, `src`, `output/figures`, `output/tables`, `notebooks`)
2. Create `requirements.txt` with all dependencies
3. Create a simple `src/utils.py` with shared utilities (logging, paths)
4. Install dependencies

### Validation Test
```bash
# Test: All directories exist and Python can import dependencies
python -c "
import pandas, numpy, requests, bs4, sodapy, statsmodels, matplotlib, seaborn
from pathlib import Path
dirs = ['data/raw', 'data/processed', 'data/analysis', 'src', 'output/figures', 'output/tables', 'notebooks']
assert all(Path(d).exists() for d in dirs), 'Missing directories'
print('CHUNK 0 PASSED: Setup complete')
"
```

### Expected Output
- All directories created
- `requirements.txt` exists
- All imports succeed

---

## Chunk 1: Steam Charts Player Data Collection
**Goal**: Scrape player count data for GTA V and comparison games.

### Tasks
1. Create `src/collect_player_data.py`
2. Scrape monthly player counts from Steam Charts for:
   - GTA V (App ID: 271590)
   - Elden Ring (App ID: 1245620)
   - Halo Infinite (App ID: 1240440)
   - Fallout 4 (App ID: 377160)
3. Handle rate limiting (1 second delay between requests)
4. Save to `data/raw/player_counts.csv`

### Validation Test
```bash
python -c "
import pandas as pd
df = pd.read_csv('data/raw/player_counts.csv')
# Must have required columns
assert set(['game', 'date', 'avg_players', 'peak_players']).issubset(df.columns), 'Missing columns'
# Must have GTA V data
assert 'GTA V' in df['game'].values, 'Missing GTA V data'
# Must have at least 2 years of data for GTA V
gta = df[df['game'] == 'GTA V']
assert len(gta) >= 24, f'Insufficient GTA V data: {len(gta)} rows'
# Player counts should be positive
assert (df['avg_players'] > 0).all(), 'Invalid player counts'
print(f'CHUNK 1 PASSED: {len(df)} rows, {df.game.nunique()} games')
"
```

### Expected Output
- `data/raw/player_counts.csv` with ~100+ rows
- Data for all 4 games (where available on Steam)
- Monthly data from 2015 onwards

---

## Chunk 2: NYC Violation Data Collection
**Goal**: Pull red light and speed camera violations from NYC Open Data.

### Tasks
1. Create `src/collect_nyc_violations.py`
2. Use Socrata API (sodapy) to pull:
   - Red Light Camera Violations (jrqf-3d3i)
   - Speed Camera Violations (need to find dataset ID)
3. Paginate through all results (datasets may have millions of rows)
4. Save to `data/raw/nyc_redlight_violations.csv` and `data/raw/nyc_speed_violations.csv`

### Validation Test
```bash
python -c "
import pandas as pd
from pathlib import Path

# Check red light data exists
rl_path = Path('data/raw/nyc_redlight_violations.csv')
assert rl_path.exists(), 'Missing red light file'
rl = pd.read_csv(rl_path)
print(f'Red light violations: {len(rl):,} rows')

# Must have date column
assert any('date' in c.lower() for c in rl.columns), f'No date column in: {rl.columns.tolist()}'

# Check date range spans multiple years
rl['_date'] = pd.to_datetime(rl[rl.columns[rl.columns.str.lower().str.contains('date')][0]])
years = rl['_date'].dt.year.nunique()
assert years >= 3, f'Only {years} years of data'

print(f'CHUNK 2 PASSED: NYC data covers {years} years')
"
```

### Expected Output
- `data/raw/nyc_redlight_violations.csv` with millions of rows
- `data/raw/nyc_speed_violations.csv` (if available)
- Date range covering 2015-present

---

## Chunk 3: Chicago Violation Data Collection
**Goal**: Pull red light and speed camera violations from Chicago Data Portal.

### Tasks
1. Create `src/collect_chicago_violations.py`
2. Use Socrata API to pull:
   - Speed Camera Violations (hhkd-xvj4)
   - Red Light Camera Violations (spqx-js37)
3. Paginate through all results
4. Save to `data/raw/chicago_speed_violations.csv` and `data/raw/chicago_redlight_violations.csv`

### Validation Test
```bash
python -c "
import pandas as pd
from pathlib import Path

speed = pd.read_csv('data/raw/chicago_speed_violations.csv')
redlight = pd.read_csv('data/raw/chicago_redlight_violations.csv')

print(f'Chicago speed violations: {len(speed):,} rows')
print(f'Chicago red light violations: {len(redlight):,} rows')

# Both should have substantial data
assert len(speed) >= 10000, 'Insufficient speed data'
assert len(redlight) >= 10000, 'Insufficient red light data'

print('CHUNK 3 PASSED: Chicago data collected')
"
```

### Expected Output
- `data/raw/chicago_speed_violations.csv`
- `data/raw/chicago_redlight_violations.csv`
- Each file with 10k+ rows

---

## Chunk 4: Player Data Processing & Stabilization Analysis
**Goal**: Process player data, fit decay curves, identify stabilization dates.

### Tasks
1. Create `src/process_player_data.py`
2. For each game:
   - Identify release date (from known dates)
   - Calculate days-since-release
   - Fit exponential decay to post-release player counts
   - Identify stabilization point (when daily change < 5% of peak)
3. Save `data/processed/release_windows.csv`
4. Generate player engagement curve plots in `output/figures/`

### Validation Test
```bash
python -c "
import pandas as pd
from pathlib import Path

# Check output exists
rw = pd.read_csv('data/processed/release_windows.csv')
print(rw)

# Required columns
required = ['game', 'release_date', 'peak_date', 'stabilization_date', 'recommended_lag_days']
assert all(c in rw.columns for c in required), f'Missing columns. Got: {rw.columns.tolist()}'

# GTA V must be present
assert 'GTA V' in rw['game'].values, 'Missing GTA V'

# Lag should be reasonable (7-60 days)
assert rw['recommended_lag_days'].between(7, 60).all(), 'Unreasonable lag values'

# Plots should exist
plots = list(Path('output/figures').glob('player_curve_*.png'))
assert len(plots) >= 1, 'No player curve plots generated'

print(f'CHUNK 4 PASSED: {len(rw)} releases processed, {len(plots)} plots generated')
"
```

### Expected Output
- `data/processed/release_windows.csv` with 4-5 rows
- Player engagement plots in `output/figures/`
- Reasonable lag recommendations (typically 14-30 days)

---

## Chunk 5: Violation Data Processing
**Goal**: Standardize and aggregate violation data from all cities.

### Tasks
1. Create `src/process_violations.py`
2. Load raw data from NYC and Chicago
3. Standardize schema: `city, date, hour, day_of_week, violation_type, count, camera_id`
4. Aggregate to daily counts
5. Create hourly aggregates if time data available
6. Save `data/processed/daily_violations.csv` and `data/processed/hourly_violations.csv`

### Validation Test
```bash
python -c "
import pandas as pd

daily = pd.read_csv('data/processed/daily_violations.csv')
print(f'Daily violations: {len(daily):,} rows')

# Required columns
assert set(['city', 'date', 'violation_type', 'count']).issubset(daily.columns)

# Multiple cities
assert daily['city'].nunique() >= 2, 'Need data from multiple cities'

# Both violation types
assert set(['redlight', 'speed']).issubset(daily['violation_type'].unique())

# Date range check
daily['date'] = pd.to_datetime(daily['date'])
date_range = daily['date'].max() - daily['date'].min()
assert date_range.days >= 365, 'Need at least 1 year of data'

# Counts should be positive
assert (daily['count'] > 0).all()

print(f'CHUNK 5 PASSED: {daily.city.nunique()} cities, {date_range.days} days of data')
"
```

### Expected Output
- `data/processed/daily_violations.csv` with thousands of rows
- Optional: `data/processed/hourly_violations.csv`
- Data from NYC and Chicago, both violation types

---

## Chunk 6: Analysis Dataset Creation
**Goal**: Tag violations with treatment windows, periods, and release identifiers.

### Tasks
1. Create `src/create_analysis_dataset.py`
2. Load processed violations and release windows
3. For each release, define:
   - Treatment window: `[stabilization_date, stabilization_date + 28 days]`
   - Pre-period: `[release_date - 42 days, release_date - 14 days]`
4. Tag each day with: `period` (pre/post/outside), `treatment` (gta_release/comparison_game/reference_year), `release_id`
5. Create reference year windows (same calendar dates, different year)
6. Save `data/analysis/tagged_violations.csv`

### Validation Test
```bash
python -c "
import pandas as pd

tagged = pd.read_csv('data/analysis/tagged_violations.csv')
print(f'Tagged violations: {len(tagged):,} rows')

# Required columns
required = ['city', 'date', 'violation_type', 'count', 'period', 'treatment', 'release_id']
assert all(c in tagged.columns for c in required), f'Missing columns. Got: {tagged.columns.tolist()}'

# Should have pre and post periods
assert 'pre' in tagged['period'].values, 'Missing pre period'
assert 'post' in tagged['period'].values, 'Missing post period'

# Should have GTA treatment
assert any('gta' in str(t).lower() for t in tagged['treatment'].unique()), 'Missing GTA treatment'

# Print summary
print('Treatment distribution:')
print(tagged.groupby(['treatment', 'period'])['count'].sum())

print('CHUNK 6 PASSED: Analysis dataset created')
"
```

### Expected Output
- `data/analysis/tagged_violations.csv`
- Proper period tagging (pre/post/outside)
- GTA and comparison game treatments identified

---

## Chunk 7: Difference-in-Differences Analysis
**Goal**: Run main DiD regression and robustness checks.

### Tasks
1. Create `src/analysis_did.py`
2. Implement DiD model: `violations = β0 + β1(post) + β2(gta) + β3(post × gta) + ε`
3. Run with multiple lag windows (1, 2, 3, 4 weeks)
4. Run placebo test with comparison games
5. Include city fixed effects
6. Save regression tables to `output/tables/`
7. Generate coefficient plots to `output/figures/`

### Validation Test
```bash
python -c "
import pandas as pd
from pathlib import Path

# Check tables exist
tables = list(Path('output/tables').glob('did_*.csv'))
assert len(tables) >= 1, 'No DiD tables generated'

# Check figures exist
figs = list(Path('output/figures').glob('did_*.png'))
assert len(figs) >= 1, 'No DiD plots generated'

# Read a results table
results = pd.read_csv(tables[0])
print(results)

# Should have coefficient estimates
assert 'coefficient' in results.columns.str.lower().str.cat() or 'coef' in results.columns.str.lower().str.cat()

print(f'CHUNK 7 PASSED: {len(tables)} tables, {len(figs)} figures')
"
```

### Expected Output
- `output/tables/did_results.csv` with regression coefficients
- `output/figures/did_coefficients.png` showing treatment effects
- Robustness tables for different lag windows

---

## Chunk 8: Time-of-Day Analysis (Conditional)
**Goal**: Analyze hourly patterns if time data is available.

### Tasks
1. Create `src/analysis_time_of_day.py`
2. Check if hourly data exists; if not, skip gracefully
3. Calculate hourly violation distribution for pre/post periods
4. Test for shifts in evening (7-10pm) and morning (7-9am) violations
5. Generate hourly distribution plots

### Validation Test
```bash
python -c "
from pathlib import Path

hourly_data = Path('data/processed/hourly_violations.csv')
if not hourly_data.exists():
    print('CHUNK 8 SKIPPED: No hourly data available')
else:
    figs = list(Path('output/figures').glob('hourly_*.png'))
    assert len(figs) >= 1, 'No hourly plots generated'
    print(f'CHUNK 8 PASSED: {len(figs)} hourly plots generated')
"
```

### Expected Output
- If hourly data: `output/figures/hourly_distribution.png`
- If no hourly data: Script exits gracefully with message

---

## Chunk 9: Day-of-Week and Event Study Analysis
**Goal**: Analyze weekly patterns and create event study visualization.

### Tasks
1. Create `src/analysis_day_of_week.py`
   - Compare day-of-week patterns in treatment vs. reference periods
   - Focus on weekend-to-Monday transitions
2. Create `src/analysis_event_study.py`
   - Center violations on release date (day 0)
   - Plot daily violations from day -30 to day +60
   - Mark release date, stabilization date, and analysis window end

### Validation Test
```bash
python -c "
from pathlib import Path

# Day of week plots
dow_figs = list(Path('output/figures').glob('*day_of_week*.png'))
assert len(dow_figs) >= 1, 'No day-of-week plots'

# Event study plots
es_figs = list(Path('output/figures').glob('event_study*.png'))
assert len(es_figs) >= 1, 'No event study plots'

print(f'CHUNK 9 PASSED: {len(dow_figs)} day-of-week plots, {len(es_figs)} event study plots')
"
```

### Expected Output
- `output/figures/day_of_week_comparison.png`
- `output/figures/event_study_gta.png`

---

## Chunk 10: Summary Statistics and Final Report
**Goal**: Generate summary tables and final report compilation.

### Tasks
1. Create `src/generate_summary.py`
2. Generate summary statistics table:
   - Violations by city, year, violation type
   - Mean, median, std of daily counts
3. Generate release windows table (formatted)
4. Compile all figures and tables into `output/` with clear naming
5. Update README with results summary

### Validation Test
```bash
python -c "
from pathlib import Path

# Summary tables
tables = list(Path('output/tables').glob('*.csv'))
assert len(tables) >= 3, f'Expected at least 3 tables, got {len(tables)}'

# Figures
figs = list(Path('output/figures').glob('*.png'))
assert len(figs) >= 4, f'Expected at least 4 figures, got {len(figs)}'

# List all outputs
print('FINAL OUTPUTS:')
print('\\nTables:')
for t in sorted(tables):
    print(f'  - {t.name}')
print('\\nFigures:')
for f in sorted(figs):
    print(f'  - {f.name}')

print(f'\\nCHUNK 10 PASSED: Project complete with {len(tables)} tables and {len(figs)} figures')
"
```

### Expected Output
- `output/tables/summary_statistics.csv`
- `output/tables/release_windows.csv`
- All figures from previous chunks
- Updated README

---

## Execution Summary

| Chunk | Name | Estimated Complexity | Dependencies |
|-------|------|---------------------|--------------|
| 0 | Setup | Low | None |
| 1 | Steam Data | Medium | Chunk 0 |
| 2 | NYC Data | Medium | Chunk 0 |
| 3 | Chicago Data | Medium | Chunk 0 |
| 4 | Process Players | Medium | Chunk 1 |
| 5 | Process Violations | Medium | Chunks 2, 3 |
| 6 | Analysis Dataset | Medium | Chunks 4, 5 |
| 7 | DiD Analysis | High | Chunk 6 |
| 8 | Time-of-Day | Medium | Chunk 6 |
| 9 | Event Study | Medium | Chunk 6 |
| 10 | Summary | Low | Chunks 7-9 |

**Parallelization**: Chunks 1-3 can run in parallel after Chunk 0. Chunks 7-9 can run in parallel after Chunk 6.

---

## Quick Reference: Running Validation Tests

After implementing each chunk, run its validation test. If it passes, proceed. If it fails, fix before moving on.

```bash
# Example: After completing Chunk 1
python -c "<paste validation test code>"
```

Or create a `tests/test_chunk_N.py` for each chunk for more robust testing.
