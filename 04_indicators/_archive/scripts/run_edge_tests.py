"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 04: INDICATOR EDGE TESTING v1.0
CLI Edge Test Runner
XIII Trading LLC
================================================================================

Runs all indicator edge tests and outputs results to terminal.
Called by the PyQt GUI via QProcess.

Usage:
    python run_edge_tests.py                           # Run all tests
    python run_edge_tests.py --indicators candle_range,volume_delta
    python run_edge_tests.py --date-from 2026-01-01
    python run_edge_tests.py --stop-type zone_buffer
    python run_edge_tests.py --export results.md

================================================================================
"""
import sys
from pathlib import Path
import argparse
from datetime import datetime
from typing import List, Dict, Optional
import traceback

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import INDICATORS, DEFAULT_INDICATOR_ORDER, RESULTS_DIR
from edge_testing.base_tester import fetch_indicator_data, EdgeTestResult
from edge_testing.edge_tests import ALL_TESTS


def print_header():
    """Print script header."""
    print("=" * 70)
    print("EPOCH INDICATOR EDGE TESTING v1.0")
    print("Statistical Edge Analysis for M1 Bar Indicators")
    print("XIII Trading LLC")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def print_section(title: str):
    """Print section header."""
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def run_indicator_tests(
    df,
    indicator_key: str,
    segments: List[tuple] = None
) -> List[EdgeTestResult]:
    """Run all tests for a single indicator across segments."""
    results = []

    if indicator_key not in ALL_TESTS:
        print(f"  No tests defined for {indicator_key}")
        return results

    tests = ALL_TESTS[indicator_key]
    indicator_name = INDICATORS[indicator_key]['name']

    print(f"\n  Testing {indicator_name}...")

    # Default segments
    if segments is None:
        segments = [
            ("ALL", None),
            ("LONG", {"direction": "LONG"}),
            ("SHORT", {"direction": "SHORT"}),
            ("CONTINUATION", {"models": ["EPCH1", "EPCH3"]}),
            ("REJECTION", {"models": ["EPCH2", "EPCH4"]}),
        ]

    for test_name, test_func in tests:
        print(f"    - {test_name}...")

        for segment_name, segment_filter in segments:
            # Apply segment filter
            if segment_filter is None:
                segment_df = df.copy()
            elif 'direction' in segment_filter:
                segment_df = df[df['direction'] == segment_filter['direction']].copy()
            elif 'models' in segment_filter:
                segment_df = df[df['model'].isin(segment_filter['models'])].copy()
            elif 'model' in segment_filter:
                segment_df = df[df['model'] == segment_filter['model']].copy()
            else:
                segment_df = df.copy()

            if len(segment_df) < 30:
                continue

            try:
                result = test_func(segment_df, segment_name)
                results.append(result)
            except Exception as e:
                print(f"      ERROR in {segment_name}: {e}")

    return results


def print_results_summary(all_results: List[EdgeTestResult]):
    """Print summary of all test results."""
    print_section("RESULTS SUMMARY")

    edges_found = [r for r in all_results if r.has_edge]
    no_edge = [r for r in all_results if not r.has_edge and r.confidence != "LOW"]
    insufficient = [r for r in all_results if r.confidence == "LOW"]

    print(f"\n  Total Tests Run: {len(all_results)}")
    print(f"  Edges Detected: {len(edges_found)}")
    print(f"  No Edge: {len(no_edge)}")
    print(f"  Insufficient Data: {len(insufficient)}")

    if edges_found:
        print("\n  EDGES DETECTED:")
        print("-" * 70)

        # Sort by effect size descending
        edges_found.sort(key=lambda x: x.effect_size, reverse=True)

        for result in edges_found:
            status = "[+]" if result.confidence == "HIGH" else "[~]"
            print(f"  {status} {result.indicator} - {result.test_name} ({result.segment})")
            print(f"      Effect: {result.effect_size:.1f}pp | p={result.p_value:.4f} | {result.confidence}")

            # Show group win rates
            if result.groups:
                groups_str = ", ".join([
                    f"{k}: {v['win_rate']:.1f}% ({v['trades']})"
                    for k, v in sorted(result.groups.items(), key=lambda x: x[1]['win_rate'], reverse=True)
                ])
                print(f"      Groups: {groups_str}")

    print()


def print_detailed_results(all_results: List[EdgeTestResult], indicator_key: str = None):
    """Print detailed results for each indicator."""
    # Group by indicator
    by_indicator = {}
    for r in all_results:
        if indicator_key and r.indicator.lower().replace(' ', '_') != indicator_key:
            continue
        if r.indicator not in by_indicator:
            by_indicator[r.indicator] = []
        by_indicator[r.indicator].append(r)

    for indicator, results in by_indicator.items():
        print_section(f"{indicator.upper()} RESULTS")

        # Group by test name
        by_test = {}
        for r in results:
            if r.test_name not in by_test:
                by_test[r.test_name] = []
            by_test[r.test_name].append(r)

        for test_name, test_results in by_test.items():
            print(f"\n  {test_name}:")
            print("-" * 60)

            for r in test_results:
                if r.has_edge:
                    status = "EDGE"
                    color_code = ""  # Terminal will show as-is
                elif r.confidence == "LOW":
                    status = "LOW_DATA"
                else:
                    status = "NO_EDGE"

                print(f"    {r.segment:20} | {status:10} | Effect: {r.effect_size:5.1f}pp | p={r.p_value:.4f}")

                if r.groups and r.has_edge:
                    for group, data in sorted(r.groups.items(), key=lambda x: x[1]['win_rate'], reverse=True):
                        print(f"      - {group}: {data['win_rate']:.1f}% WR ({data['trades']} trades)")


def generate_markdown_report(all_results: List[EdgeTestResult], metadata: Dict) -> str:
    """Generate a markdown report of all results."""
    lines = [
        "# Indicator Edge Test Results",
        "",
        f"**Generated:** {metadata.get('timestamp', datetime.now().isoformat())}",
        f"**Total Trades:** {metadata.get('total_trades', 'N/A'):,}",
        f"**Baseline Win Rate:** {metadata.get('baseline_win_rate', 'N/A'):.1f}%",
        f"**Stop Type:** {metadata.get('stop_type', 'zone_buffer')}",
        "",
        "---",
        "",
        "## Summary",
        "",
    ]

    edges_found = [r for r in all_results if r.has_edge]
    lines.append(f"- **Edges Detected:** {len(edges_found)}")
    lines.append(f"- **Tests Run:** {len(all_results)}")
    lines.append("")

    if edges_found:
        lines.append("## Validated Edges")
        lines.append("")
        lines.append("| Indicator | Test | Segment | Effect | p-value | Confidence |")
        lines.append("|-----------|------|---------|--------|---------|------------|")

        for r in sorted(edges_found, key=lambda x: x.effect_size, reverse=True):
            lines.append(f"| {r.indicator} | {r.test_name} | {r.segment} | {r.effect_size:.1f}pp | {r.p_value:.4f} | {r.confidence} |")

        lines.append("")

    # Detailed results by indicator
    lines.append("## Detailed Results")
    lines.append("")

    by_indicator = {}
    for r in all_results:
        if r.indicator not in by_indicator:
            by_indicator[r.indicator] = []
        by_indicator[r.indicator].append(r)

    for indicator, results in by_indicator.items():
        lines.append(f"### {indicator}")
        lines.append("")

        for r in results:
            status = "EDGE" if r.has_edge else ("LOW DATA" if r.confidence == "LOW" else "NO EDGE")
            lines.append(f"- **{r.test_name}** ({r.segment}): {status}")
            if r.has_edge:
                lines.append(f"  - Effect: {r.effect_size:.1f}pp, p={r.p_value:.4f}")

        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Run indicator edge tests for statistical validation"
    )
    parser.add_argument(
        '--indicators',
        type=str,
        default=None,
        help='Comma-separated list of indicators to test (default: all)'
    )
    parser.add_argument(
        '--date-from',
        type=str,
        default=None,
        help='Start date filter (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--date-to',
        type=str,
        default=None,
        help='End date filter (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--stop-type',
        type=str,
        default='zone_buffer',
        help='Stop type for win/loss definition (default: zone_buffer)'
    )
    parser.add_argument(
        '--export',
        type=str,
        default=None,
        help='Export results to markdown file'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed output'
    )

    args = parser.parse_args()

    # Print header
    print_header()

    # Parse indicators
    if args.indicators:
        indicators = [i.strip() for i in args.indicators.split(',')]
    else:
        indicators = DEFAULT_INDICATOR_ORDER

    # Validate indicators
    for ind in indicators:
        if ind not in INDICATORS:
            print(f"ERROR: Unknown indicator '{ind}'")
            print(f"Available: {', '.join(INDICATORS.keys())}")
            sys.exit(1)

    print(f"\nIndicators: {', '.join(indicators)}")
    print(f"Stop Type: {args.stop_type}")
    if args.date_from:
        print(f"Date From: {args.date_from}")
    if args.date_to:
        print(f"Date To: {args.date_to}")

    # Fetch data
    print_section("LOADING DATA")
    print("\n[1/3] Connecting to Supabase...")

    try:
        df = fetch_indicator_data(
            date_from=args.date_from,
            date_to=args.date_to,
            stop_type=args.stop_type
        )
    except Exception as e:
        print(f"ERROR: Failed to fetch data: {e}")
        traceback.print_exc()
        sys.exit(1)

    if df.empty:
        print("ERROR: No data returned from database")
        sys.exit(1)

    print(f"  Connected successfully")
    print(f"\n[2/3] Data loaded: {len(df):,} trades")
    print(f"  Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"  Baseline win rate: {df['is_winner'].mean()*100:.1f}%")

    # Check indicator data availability
    print(f"\n[3/3] Indicator data availability:")
    indicator_cols = ['vol_delta', 'vol_roc', 'cvd_slope', 'sma_spread', 'h1_structure']
    for col in indicator_cols:
        if col in df.columns:
            valid = df[col].notna().sum()
            pct = valid / len(df) * 100
            print(f"  {col}: {valid:,} ({pct:.1f}%)")

    # Build metadata
    metadata = {
        'timestamp': datetime.now().isoformat(),
        'total_trades': len(df),
        'baseline_win_rate': df['is_winner'].mean() * 100,
        'stop_type': args.stop_type,
        'date_from': args.date_from,
        'date_to': args.date_to
    }

    # Run tests
    print_section("RUNNING EDGE TESTS")
    print(f"\nTesting {len(indicators)} indicator(s)...")

    all_results = []

    for i, indicator_key in enumerate(indicators, 1):
        print(f"\n[{i}/{len(indicators)}] {INDICATORS[indicator_key]['name']}...")

        try:
            results = run_indicator_tests(df, indicator_key)
            all_results.extend(results)

            edges = sum(1 for r in results if r.has_edge)
            print(f"    Completed: {len(results)} tests, {edges} edges found")

        except Exception as e:
            print(f"    ERROR: {e}")
            if args.verbose:
                traceback.print_exc()

    # Print results
    print_results_summary(all_results)

    if args.verbose:
        print_detailed_results(all_results)

    # Export if requested
    if args.export:
        RESULTS_DIR.mkdir(exist_ok=True)
        report = generate_markdown_report(all_results, metadata)
        export_path = RESULTS_DIR / args.export
        with open(export_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\nReport exported to: {export_path}")

    # Final summary
    print("=" * 70)
    print("ALL COMPLETE")
    print("=" * 70)

    edges_count = sum(1 for r in all_results if r.has_edge)
    if edges_count > 0:
        print(f"\n  {edges_count} validated edges found!")
    else:
        print(f"\n  No significant edges detected.")


if __name__ == "__main__":
    main()
