# Claude Code Spec: GTA Release and Traffic Violation Analysis

## Project Overview

Build a data pipeline and analysis to test whether Grand Theft Auto releases are associated with increases in automated traffic enforcement violations, using a time-lagged design to separate priming effects from incapacitation effects.

---

## Phase 1: Data Collection

### 1.1 Game Release and Player Data

**Objective**: Get GTA release dates and player engagement curves to (a) define treatment windows and (b) data-drive the optimal lag period.

**Steam Charts Scrape** (for PC data):
```
URL pattern: https://steamcharts.com/app/271590 (GTA V)
Need: Daily or monthly player counts
Fields: date, avg_players, peak_players
```

**Key dates to hardcode as fallback**:
- GTA V Console: September 17, 2013
- GTA V PC: April 14, 2015
- GTA Online major updates: will need to research, but heists update (March 2015), etc.

**Comparison games** (non-driving, similar scale releases):
- Elden Ring: February 25, 2022 (Steam App ID: 1245620)
- Halo Infinite: December 8, 2021 (Steam App ID: 1240440)
- Skyrim: November 11, 2011
- Fallout 4: November 10, 2015

Pull Steam Charts data for these as well for player curve comparison.

**Output**: `data/raw/player_counts.csv` with columns: `game, date, avg_players, peak_players`

---

### 1.2 NYC Traffic Camera Violations

**Source**: NYC Open Data

**Red Light Camera Violations**:
```
Dataset: "Red Light Camera Violations"
URL: https://data.cityofnewyork.us/Transportation/Red-Light-Camera-Violations/jrqf-3d3i
API endpoint: https://data.cityofnewyork.us/resource/jrqf-3d3i.json
```

**Speed Camera Violations**:
```
Dataset: "School Speed Camera Violations" (may have different naming)
Search NYC Open Data for current dataset name
```

**Fields needed**:
- violation_date (or issue_date)
- violation_time (if available)
- location/camera_id (for potential geographic analysis)
- violation_count or individual records

**Pull strategy**:
- If API has row limits, paginate using $offset and $limit
- Pull all available years
- Save as `data/raw/nyc_redlight_violations.csv` and `data/raw/nyc_speed_violations.csv`

---

### 1.3 Chicago Traffic Camera Data (Secondary)

**Source**: Chicago Data Portal

**Speed Camera Violations**:
```
Dataset: "Speed Camera Violations"
URL: https://data.cityofchicago.org/Transportation/Speed-Camera-Violations/hhkd-xvj4
API endpoint: https://data.cityofchicago.org/resource/hhkd-xvj4.json
```

**Red Light Camera Violations**:
```
Dataset: "Red Light Camera Violations"  
URL: https://data.cityofchicago.org/Transportation/Red-Light-Camera-Violations/spqx-js37
API endpoint: https://data.cityofchicago.org/resource/spqx-js37.json
```

**Fields**: Similar to NYC — date, time if available, location, count

**Output**: `data/raw/chicago_speed_violations.csv`, `data/raw/chicago_redlight_violations.csv`

---

### 1.4 DC Traffic Camera Data (Tertiary, if time permits)

Check DC Open Data portal for similar datasets.

---

## Phase 2: Data Processing

### 2.1 Player Data Processing

**Script**: `src/process_player_data.py`

**Tasks**:
1. Load player count data
2. For each game release:
   - Identify release date
   - Calculate days-since-release
   - Fit a decay curve to post-release player counts (exponential decay or similar)
   - Identify "stabilization point" — when daily change drops below X% threshold
   - This becomes the data-driven lag window (expected: ~2-3 weeks)

**Output**: 
- `data/processed/release_windows.csv`: `game, release_date, peak_date, stabilization_date, recommended_lag_days`
- Plots of player curves with stabilization points marked

---

### 2.2 Violation Data Processing

**Script**: `src/process_violations.py`

**Tasks**:
1. Load violation data from each city
2. Standardize schema:
   - `city`: string
   - `date`: date
   - `hour`: int (0-23), if available; else null
   - `day_of_week`: int (0=Monday, 6=Sunday)
   - `violation_type`: 'redlight' | 'speed'
   - `count`: int (1 if individual records, else aggregated count)
   - `camera_id`: string, if available
3. Aggregate to daily counts by city and violation type
4. If hourly data available, also create hourly aggregates

**Output**:
- `data/processed/daily_violations.csv`: `city, date, violation_type, count`
- `data/processed/hourly_violations.csv`: `city, date, hour, violation_type, count` (if time data available)

---

### 2.3 Create Analysis Dataset

**Script**: `src/create_analysis_dataset.py`

**Tasks**:
1. Load processed violations and release windows
2. For each GTA release:
   - Define treatment window: `[stabilization_date, stabilization_date + 28 days]`
   - Define pre-period: `[release_date - 42 days, release_date - 14 days]` (avoid immediate pre-release hype period)
3. For each comparison game release:
   - Same window structure
4. For reference years (no major release):
   - Same calendar windows
5. Tag each day in violations data with:
   - `period`: 'pre' | 'post' | 'outside'
   - `treatment`: 'gta_release' | 'comparison_game' | 'reference_year'
   - `release_id`: identifier for which specific release/comparison

**Output**: `data/analysis/tagged_violations.csv`

---

## Phase 3: Analysis

### 3.1 Basic Difference-in-Differences

**Script**: `src/analysis_did.py`

**Model**:
```
violations_it = β0 + β1(post_t) + β2(gta_release_i) + β3(post_t × gta_release_i) + ε_it
```

Where:
- `violations_it` = daily violation count (possibly log-transformed or per-camera)
- `post_t` = indicator for post-stabilization period
- `gta_release_i` = indicator for GTA release window (vs. reference year)
- `β3` = treatment effect of interest

**Robustness**:
- Vary lag window (1, 2, 3, 4 weeks post-stabilization)
- Compare GTA vs. non-driving games (placebo test)
- City fixed effects if pooling

**Output**: 
- Regression tables
- Coefficient plots with confidence intervals across lag specifications

---

### 3.2 Time-of-Day Analysis

**Script**: `src/analysis_time_of_day.py`

**Only if hourly data available**

**Approach**:
1. Calculate hourly distribution of violations for:
   - GTA post-period
   - GTA pre-period
   - Reference year same calendar window
2. Test for:
   - Decrease in evening violations (7-10pm) → incapacitation
   - Increase in morning violations (7-9am) → priming (played last night)

**Visualization**:
- Hourly violation density plots, overlaid by period
- Difference plot (post minus pre) by hour

---

### 3.3 Day-of-Week Analysis

**Script**: `src/analysis_day_of_week.py`

**Approach**:
1. Hypothesis: Weekend evening gaming → Monday/Sunday morning aggressive driving
2. Compare day-of-week violation patterns in treatment vs. reference periods
3. Look specifically at:
   - Saturday night → Sunday morning shift
   - Friday night → Saturday morning shift

---

### 3.4 Event Study Visualization

**Script**: `src/analysis_event_study.py`

**Approach**:
1. Center all violations on release date (day 0)
2. Plot daily violations from day -30 to day +60
3. Mark key points:
   - Release date
   - Data-driven stabilization date
   - End of analysis window

**Output**: Event study plot showing violation trajectory around releases

---

## Phase 4: Output and Reporting

### 4.1 Figures to Generate

1. **Player engagement curves** with stabilization points marked
2. **Event study plots** for each city and violation type
3. **DiD coefficient plots** across lag specifications
4. **Time-of-day distribution shifts** (if hourly data)
5. **Comparison: GTA vs. non-driving games** 

### 4.2 Tables to Generate

1. **Summary statistics**: Violations by city, year, violation type
2. **Release windows**: All releases analyzed with dates
3. **Main DiD results**: Treatment effects with SEs, p-values
4. **Robustness checks**: Varying lag windows, different comparison groups

---

## Directory Structure

```
gta-driving-behavior/
├── README.md
├── SPEC.md (this file)
├── data/
│   ├── raw/
│   │   ├── player_counts.csv
│   │   ├── nyc_redlight_violations.csv
│   │   ├── nyc_speed_violations.csv
│   │   ├── chicago_speed_violations.csv
│   │   └── chicago_redlight_violations.csv
│   ├── processed/
│   │   ├── release_windows.csv
│   │   ├── daily_violations.csv
│   │   └── hourly_violations.csv
│   └── analysis/
│       └── tagged_violations.csv
├── src/
│   ├── collect_player_data.py
│   ├── collect_nyc_violations.py
│   ├── collect_chicago_violations.py
│   ├── process_player_data.py
│   ├── process_violations.py
│   ├── create_analysis_dataset.py
│   ├── analysis_did.py
│   ├── analysis_time_of_day.py
│   ├── analysis_day_of_week.py
│   └── analysis_event_study.py
├── output/
│   ├── figures/
│   └── tables/
└── notebooks/
    └── exploratory.ipynb
```

---

## Dependencies

```
pandas
numpy
requests
beautifulsoup4 (for Steam Charts scraping)
sodapy (for Socrata API - NYC/Chicago Open Data)
statsmodels (for regression)
matplotlib
seaborn
```

---

## Execution Order

1. `collect_player_data.py`
2. `collect_nyc_violations.py`
3. `collect_chicago_violations.py`
4. `process_player_data.py`
5. `process_violations.py`
6. `create_analysis_dataset.py`
7. `analysis_did.py`
8. `analysis_time_of_day.py` (if hourly data)
9. `analysis_day_of_week.py`
10. `analysis_event_study.py`

---

## Notes for Implementation

- **Rate limiting**: NYC and Chicago APIs may have rate limits. Add delays between requests.
- **Data size**: Violation datasets may be large (millions of rows). Consider chunked processing.
- **Missing time data**: If violation time isn't available, skip time-of-day analysis rather than imputing.
- **Statistical inference**: Cluster standard errors by camera or use Newey-West for time series autocorrelation.
- **Interpretation**: Remember this is exploratory/descriptive. We can't link violations to individual gamers, only population-level patterns.
