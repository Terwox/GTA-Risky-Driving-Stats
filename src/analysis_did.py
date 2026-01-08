"""
Chunk 7: Difference-in-Differences Analysis.

Runs the main DiD regression comparing GTA release periods to:
- Comparison game releases (placebo)
- Reference year same-date windows (control)

Model: violations = β0 + β1(post) + β2(gta) + β3(post × gta) + city_FE + ε

The key coefficient of interest is β3 (the interaction term).
"""

import pandas as pd
import numpy as np
import statsmodels.api as sm
import statsmodels.formula.api as smf
import matplotlib.pyplot as plt
from pathlib import Path

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import DATA_ANALYSIS, OUTPUT_FIGURES, OUTPUT_TABLES, setup_logging, ensure_dirs

logger = setup_logging(__name__)


def load_analysis_data():
    """Load the tagged analysis dataset."""
    path = DATA_ANALYSIS / "tagged_violations.csv"
    if not path.exists():
        logger.error(f"Analysis data not found at {path}")
        return None

    df = pd.read_csv(path)
    df['date'] = pd.to_datetime(df['date'])
    logger.info(f"Loaded {len(df):,} tagged violation records")

    return df


def run_did_regression(df: pd.DataFrame, treatment_col: str = 'gta',
                       control_col: str = 'reference') -> dict:
    """
    Run difference-in-differences regression.

    Args:
        df: Tagged violations dataframe
        treatment_col: Value in 'treatment' column for treatment group
        control_col: Value in 'treatment' column for control group

    Returns:
        Dictionary with regression results
    """
    # Filter to treatment and control groups only
    subset = df[df['treatment'].isin([treatment_col, control_col])].copy()

    if len(subset) < 10:
        logger.warning(f"Not enough data for {treatment_col} vs {control_col}")
        return None

    # Create dummy variables
    subset['is_treated'] = (subset['treatment'] == treatment_col).astype(int)
    subset['is_post'] = (subset['period'] == 'post').astype(int)
    subset['treated_x_post'] = subset['is_treated'] * subset['is_post']

    # Aggregate to daily level per group for cleaner regression
    # (avoids double-counting due to violation types)
    daily_agg = subset.groupby(['date', 'city', 'is_treated', 'is_post', 'treated_x_post']).agg({
        'count': 'sum'
    }).reset_index()

    # Ensure count is numeric
    daily_agg['count'] = pd.to_numeric(daily_agg['count'], errors='coerce')
    daily_agg = daily_agg.dropna(subset=['count'])

    # Add city dummies for fixed effects
    daily_agg = pd.get_dummies(daily_agg, columns=['city'], drop_first=True)

    # Run OLS regression
    # violations = β0 + β1(post) + β2(treated) + β3(treated_x_post) + city_FE
    y = daily_agg['count'].astype(float)
    X_cols = ['is_post', 'is_treated', 'treated_x_post']

    # Add city fixed effects if available
    city_cols = [c for c in daily_agg.columns if c.startswith('city_')]
    X_cols.extend(city_cols)

    X = daily_agg[X_cols].astype(float)
    X = sm.add_constant(X)

    model = sm.OLS(y, X).fit(cov_type='HC1')  # Robust standard errors

    logger.info(f"\nDiD Regression: {treatment_col} vs {control_col}")
    logger.info(f"N = {len(daily_agg)}")
    logger.info(f"R² = {model.rsquared:.4f}")

    return {
        'treatment': treatment_col,
        'control': control_col,
        'n_obs': len(daily_agg),
        'r_squared': model.rsquared,
        'model': model,
        'summary': model.summary()
    }


def run_all_analyses(df: pd.DataFrame) -> list:
    """Run all DiD analyses and return results."""
    results = []

    # Main analysis: GTA vs Reference years
    result = run_did_regression(df, 'gta', 'reference')
    if result:
        results.append(result)

    # Placebo test: Comparison games vs Reference years
    result = run_did_regression(df, 'comparison', 'reference')
    if result:
        results.append(result)

    # Direct comparison: GTA vs Comparison games
    result = run_did_regression(df, 'gta', 'comparison')
    if result:
        results.append(result)

    return results


def save_results_table(results: list, output_path: Path):
    """Save regression results to a CSV table."""
    rows = []

    for r in results:
        model = r['model']
        params = model.params
        pvalues = model.pvalues
        ci = model.conf_int()

        for var in ['is_post', 'is_treated', 'treated_x_post']:
            if var in params.index:
                rows.append({
                    'comparison': f"{r['treatment']} vs {r['control']}",
                    'variable': var,
                    'coefficient': params[var],
                    'std_error': model.bse[var],
                    'p_value': pvalues[var],
                    'ci_lower': ci.loc[var, 0],
                    'ci_upper': ci.loc[var, 1],
                    'n_obs': r['n_obs'],
                    'r_squared': r['r_squared']
                })

    results_df = pd.DataFrame(rows)
    results_df.to_csv(output_path, index=False)
    logger.info(f"Saved results table to {output_path}")

    return results_df


def plot_did_coefficients(results: list, output_path: Path):
    """Plot the DiD interaction coefficients with confidence intervals."""
    fig, ax = plt.subplots(figsize=(10, 6))

    y_pos = []
    labels = []
    coeffs = []
    errors = []
    colors = []

    for i, r in enumerate(results):
        model = r['model']
        if 'treated_x_post' in model.params.index:
            coef = model.params['treated_x_post']
            se = model.bse['treated_x_post']
            ci = model.conf_int().loc['treated_x_post']

            y_pos.append(i)
            labels.append(f"{r['treatment']} vs {r['control']}")
            coeffs.append(coef)
            errors.append([coef - ci[0], ci[1] - coef])

            # Color based on treatment type
            if 'gta' in r['treatment'].lower():
                colors.append('red' if 'reference' in r['control'] else 'orange')
            else:
                colors.append('blue')

    errors = np.array(errors).T

    ax.barh(y_pos, coeffs, xerr=errors, capsize=5, color=colors, alpha=0.7)
    ax.axvline(x=0, color='black', linestyle='--', alpha=0.5)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.set_xlabel('DiD Coefficient (treated × post)')
    ax.set_title('Difference-in-Differences: Effect of Game Releases on Traffic Violations')

    # Add significance indicators
    for i, r in enumerate(results):
        model = r['model']
        if 'treated_x_post' in model.params.index:
            p = model.pvalues['treated_x_post']
            if p < 0.01:
                sig = '***'
            elif p < 0.05:
                sig = '**'
            elif p < 0.1:
                sig = '*'
            else:
                sig = ''

            coef = model.params['treated_x_post']
            ax.annotate(sig, xy=(coef, i), xytext=(5, 0),
                       textcoords='offset points', fontsize=12, fontweight='bold')

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    logger.info(f"Saved coefficient plot to {output_path}")


def print_summary(results: list):
    """Print a summary of all analyses."""
    print("\n" + "=" * 60)
    print("DIFFERENCE-IN-DIFFERENCES ANALYSIS RESULTS")
    print("=" * 60)

    for r in results:
        print(f"\n{'-' * 40}")
        print(f"Comparison: {r['treatment'].upper()} vs {r['control'].upper()}")
        print(f"N = {r['n_obs']}, R² = {r['r_squared']:.4f}")
        print(f"{'-' * 40}")

        model = r['model']

        # Key result: interaction term
        if 'treated_x_post' in model.params.index:
            coef = model.params['treated_x_post']
            se = model.bse['treated_x_post']
            p = model.pvalues['treated_x_post']

            # Significance level
            if p < 0.01:
                sig = '***'
            elif p < 0.05:
                sig = '**'
            elif p < 0.1:
                sig = '*'
            else:
                sig = ''

            print(f"DiD Coefficient (treated × post): {coef:.2f} {sig}")
            print(f"  Standard Error: {se:.2f}")
            print(f"  p-value: {p:.4f}")

            # Interpretation
            if p < 0.05:
                direction = "increase" if coef > 0 else "decrease"
                print(f"\n  SIGNIFICANT: {r['treatment']} releases associated with")
                print(f"  {abs(coef):.0f} daily violations {direction} compared to {r['control']}")
            else:
                print(f"\n  NOT SIGNIFICANT at p < 0.05")


def main():
    """Main entry point for DiD analysis."""
    ensure_dirs()

    # Load data
    df = load_analysis_data()
    if df is None:
        return False

    # Run all analyses
    results = run_all_analyses(df)

    if not results:
        logger.error("No regression results generated!")
        return False

    # Save results
    results_df = save_results_table(results, OUTPUT_TABLES / "did_results.csv")

    # Plot coefficients
    plot_did_coefficients(results, OUTPUT_FIGURES / "did_coefficients.png")

    # Print summary
    print_summary(results)

    # Also save full regression summaries
    for r in results:
        summary_path = OUTPUT_TABLES / f"did_summary_{r['treatment']}_vs_{r['control']}.txt"
        with open(summary_path, 'w') as f:
            f.write(str(r['summary']))
        logger.info(f"Saved summary to {summary_path}")

    print("\n" + "=" * 60)
    print("Analysis complete. Files saved to output/tables/ and output/figures/")
    print("=" * 60)

    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
