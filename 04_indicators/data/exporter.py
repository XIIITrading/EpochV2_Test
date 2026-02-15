"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 04: INDICATOR ANALYSIS v2.0
Results Exporter - Exports analysis snapshots to files for AI consumption
XIII Trading LLC
================================================================================

Exports each tab's analysis data to structured files in /results/ so that
Claude Code, Claude Desktop, or any AI assistant can read and reason over
the trading indicator analysis.

Output per export run (timestamped folder):
  results/
    YYYY-MM-DD_HHMMSS/
      _meta.md               - Filters, trade count, export metadata
      01_ramp_up.md           - Ramp-up analysis narrative + data tables
      02_entry_snapshot.md    - Entry indicator state analysis
      03_post_trade.md        - Post-trade divergence analysis
      04_deep_dive.md         - Per-indicator three-phase breakdown
      05_composite_setup.md   - Multi-indicator combination results
      csv/
        ramp_up_averages.csv
        entry_data.csv
        post_trade_averages.csv
        deep_dive_{indicator}.csv
        setup_combinations.csv
        setup_scores.csv
"""
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from config import (
    MODULE_ROOT, RAMP_UP_BARS, POST_TRADE_BARS,
    CONTINUOUS_INDICATORS, CATEGORICAL_INDICATORS,
    ALL_DEEP_DIVE_INDICATORS, THRESHOLDS,
)
from data.provider import DataProvider


class ResultsExporter:
    """Exports indicator analysis results to structured files."""

    def __init__(self, provider: DataProvider, results_dir: Optional[Path] = None):
        self._provider = provider
        self._results_dir = results_dir or MODULE_ROOT / "results"

    def export_all(self, data: Dict, filters: Dict) -> Path:
        """
        Export all tab analyses to a timestamped results folder.

        Parameters
        ----------
        data : dict
            The data dict from MainWindow._current_data containing:
            - entry_data: pd.DataFrame
            - trade_ids: list[str]
            - ramp_up_avgs: pd.DataFrame
            - post_trade_avgs: pd.DataFrame
            - pending_count: int
        filters : dict
            Active filter state (model, direction, ticker, outcome, date_from, date_to)

        Returns
        -------
        Path to the export folder
        """
        ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        export_dir = self._results_dir / ts
        csv_dir = export_dir / "csv"
        csv_dir.mkdir(parents=True, exist_ok=True)

        entry_data = data["entry_data"]
        trade_ids = data["trade_ids"]
        ramp_up_avgs = data["ramp_up_avgs"]
        post_trade_avgs = data["post_trade_avgs"]
        pending_count = data.get("pending_count", 0)

        # --- Export all sections ---
        self._export_meta(export_dir, filters, entry_data, trade_ids, pending_count)
        self._export_ramp_up(export_dir, csv_dir, ramp_up_avgs, trade_ids)
        self._export_entry_snapshot(export_dir, csv_dir, entry_data, trade_ids)
        self._export_post_trade(export_dir, csv_dir, post_trade_avgs, trade_ids)
        self._export_deep_dive(export_dir, csv_dir, entry_data, trade_ids)
        self._export_composite(export_dir, csv_dir, entry_data, trade_ids)

        return export_dir

    # ==================================================================
    # _meta.md - Export metadata and filter context
    # ==================================================================
    def _export_meta(self, export_dir: Path, filters: Dict,
                     entry_data: pd.DataFrame, trade_ids: List[str],
                     pending_count: int):
        lines = [
            "# Epoch Indicator Analysis - Export Metadata",
            f"**Exported:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Active Filters",
            f"- **Model:** {filters.get('model') or 'All Models'}",
            f"- **Direction:** {filters.get('direction') or 'All Directions'}",
            f"- **Ticker:** {filters.get('ticker') or 'All Tickers'}",
            f"- **Outcome:** {filters.get('outcome') or 'All Trades'}",
            f"- **Date Range:** {filters.get('date_from')} to {filters.get('date_to')}",
            "",
            "## Dataset Summary",
            f"- **Total Trades:** {len(trade_ids):,}",
        ]

        if not entry_data.empty and 'is_winner' in entry_data.columns:
            winners = int(entry_data['is_winner'].sum())
            total = len(entry_data)
            win_rate = winners / total * 100 if total else 0
            avg_r = entry_data['pnl_r'].mean() if 'pnl_r' in entry_data.columns else 0
            lines.extend([
                f"- **Winners:** {winners:,}",
                f"- **Losers:** {total - winners:,}",
                f"- **Win Rate:** {win_rate:.1f}%",
                f"- **Avg R:** {avg_r:.2f}",
            ])

        if pending_count > 0:
            lines.extend([
                "",
                f"**WARNING:** {pending_count:,} trades pending indicator analysis "
                "(not included in results).",
            ])

        if not entry_data.empty and 'model' in entry_data.columns:
            lines.extend(["", "## Trade Distribution by Model"])
            model_stats = entry_data.groupby('model').agg(
                total=('is_winner', 'count'),
                wins=('is_winner', 'sum'),
            ).reset_index()
            model_stats['win_rate'] = (model_stats['wins'] / model_stats['total'] * 100).round(1)
            lines.append("")
            lines.append("| Model | Trades | Wins | Win Rate |")
            lines.append("|-------|--------|------|----------|")
            for _, row in model_stats.iterrows():
                lines.append(
                    f"| {row['model']} | {int(row['total'])} | "
                    f"{int(row['wins'])} | {row['win_rate']:.1f}% |"
                )

        if not entry_data.empty and 'direction' in entry_data.columns:
            lines.extend(["", "## Trade Distribution by Direction"])
            dir_stats = entry_data.groupby('direction').agg(
                total=('is_winner', 'count'),
                wins=('is_winner', 'sum'),
            ).reset_index()
            dir_stats['win_rate'] = (dir_stats['wins'] / dir_stats['total'] * 100).round(1)
            lines.append("")
            lines.append("| Direction | Trades | Wins | Win Rate |")
            lines.append("|-----------|--------|------|----------|")
            for _, row in dir_stats.iterrows():
                lines.append(
                    f"| {row['direction']} | {int(row['total'])} | "
                    f"{int(row['wins'])} | {row['win_rate']:.1f}% |"
                )

        lines.extend([
            "",
            "## File Index",
            "- `_meta.md` - This file (filters, dataset summary)",
            "- `01_ramp_up.md` - Pre-entry indicator progression (25 M1 bars)",
            "- `02_entry_snapshot.md` - Indicator state at the moment of entry",
            "- `03_post_trade.md` - Post-entry indicator behavior (25 M1 bars)",
            "- `04_deep_dive.md` - Per-indicator three-phase analysis",
            "- `05_composite_setup.md` - Multi-indicator combination scoring",
            "- `csv/` - Raw data files for programmatic analysis",
        ])

        (export_dir / "_meta.md").write_text("\n".join(lines), encoding="utf-8")

    # ==================================================================
    # 01_ramp_up.md - Pre-entry indicator progression
    # ==================================================================
    def _export_ramp_up(self, export_dir: Path, csv_dir: Path,
                        ramp_up_avgs: pd.DataFrame, trade_ids: List[str]):
        # Save CSV
        if not ramp_up_avgs.empty:
            ramp_up_avgs.to_csv(csv_dir / "ramp_up_averages.csv", index=False)

        lines = [
            "# 01 - Ramp-Up Analysis: Pre-Entry Indicator Progression",
            "",
            f"Analysis of average indicator values across {RAMP_UP_BARS} M1 bars before entry.",
            "Direction-normalized: Vol Delta and CVD Slope are sign-flipped for SHORT trades",
            "so that positive values always mean 'favorable for the trade direction'.",
            "",
        ]

        if ramp_up_avgs.empty:
            lines.append("**No ramp-up data available.**")
            (export_dir / "01_ramp_up.md").write_text("\n".join(lines), encoding="utf-8")
            return

        # Trade counts
        winners = ramp_up_avgs[ramp_up_avgs['is_winner'] == True]
        losers = ramp_up_avgs[ramp_up_avgs['is_winner'] == False]
        w_count = winners['trade_count'].max() if not winners.empty else 0
        l_count = losers['trade_count'].max() if not losers.empty else 0
        lines.append(f"**Winner trades:** {int(w_count):,} | **Loser trades:** {int(l_count):,}")
        lines.append("")

        # Summary stats for last 10 bars (the ramp-up zone)
        lines.append("## Ramp-Up Zone Summary (Last 10 Bars Before Entry)")
        lines.append("")

        last_10 = ramp_up_avgs[ramp_up_avgs['bar_sequence'] >= 15]
        if not last_10.empty:
            w_last = last_10[last_10['is_winner'] == True]
            l_last = last_10[last_10['is_winner'] == False]

            indicators = [
                ('avg_candle_range', 'Candle Range %'),
                ('avg_vol_delta', 'Vol Delta (normalized)'),
                ('avg_vol_roc', 'Vol ROC %'),
                ('avg_sma_spread', 'SMA Spread %'),
                ('avg_cvd_slope', 'CVD Slope (normalized)'),
            ]

            lines.append("| Indicator | Winner Avg | Loser Avg | Delta | Winner Edge |")
            lines.append("|-----------|-----------|----------|-------|-------------|")

            for col, name in indicators:
                w_avg = w_last[col].mean() if not w_last.empty else 0
                l_avg = l_last[col].mean() if not l_last.empty else 0
                delta = w_avg - l_avg
                pct = (delta / abs(l_avg) * 100) if l_avg != 0 else 0
                edge = f"+{pct:.1f}%" if pct > 0 else f"{pct:.1f}%"
                lines.append(
                    f"| {name} | {w_avg:.6f} | {l_avg:.6f} | "
                    f"{'+' if delta > 0 else ''}{delta:.6f} | {edge} |"
                )

        # Full bar-by-bar progression table
        lines.extend([
            "",
            "## Full Bar-by-Bar Progression (Winners vs Losers)",
            "",
        ])

        for is_win, label in [(True, "Winners"), (False, "Losers")]:
            subset = ramp_up_avgs[ramp_up_avgs['is_winner'] == is_win]
            if subset.empty:
                continue

            lines.append(f"### {label}")
            lines.append("")
            lines.append("| Bar | Candle Range | Vol Delta | Vol ROC | SMA Spread | CVD Slope |")
            lines.append("|-----|-------------|-----------|---------|-----------|-----------|")

            for _, row in subset.iterrows():
                lines.append(
                    f"| {int(row['bar_sequence'])} | "
                    f"{row['avg_candle_range']:.6f} | "
                    f"{row['avg_vol_delta']:.6f} | "
                    f"{row['avg_vol_roc']:.4f} | "
                    f"{row['avg_sma_spread']:.6f} | "
                    f"{row['avg_cvd_slope']:.6f} |"
                )

            lines.append("")

        # Key observations for AI
        lines.extend([
            "## Key Observations for AI Analysis",
            "",
            "When analyzing this ramp-up data, consider:",
            "1. **Divergence timing**: At which bar do winners start separating from losers?",
            "2. **Strongest signals**: Which indicator shows the most consistent winner/loser separation?",
            "3. **Acceleration**: Are indicators accelerating (rate of change increasing) before entry for winners?",
            "4. **Threshold identification**: What minimum values in the last 5-10 bars correlate with wins?",
            "5. **Combined signals**: Do multiple indicators crossing favorable thresholds simultaneously predict better outcomes?",
        ])

        (export_dir / "01_ramp_up.md").write_text("\n".join(lines), encoding="utf-8")

    # ==================================================================
    # 02_entry_snapshot.md - Indicator state at entry
    # ==================================================================
    def _export_entry_snapshot(self, export_dir: Path, csv_dir: Path,
                                entry_data: pd.DataFrame, trade_ids: List[str]):
        # Save CSV
        if not entry_data.empty:
            entry_data.to_csv(csv_dir / "entry_data.csv", index=False)

        lines = [
            "# 02 - Entry Snapshot: Indicator State at Entry",
            "",
            "Win rate breakdown by each indicator's state at the M1 bar just before entry.",
            "",
        ]

        if entry_data.empty:
            lines.append("**No entry data available.**")
            (export_dir / "02_entry_snapshot.md").write_text("\n".join(lines), encoding="utf-8")
            return

        # Overall stats
        total = len(entry_data)
        winners = int(entry_data['is_winner'].sum()) if 'is_winner' in entry_data.columns else 0
        win_rate = winners / total * 100 if total else 0
        avg_r = entry_data['pnl_r'].mean() if 'pnl_r' in entry_data.columns else 0

        lines.extend([
            f"**Total Trades:** {total:,} | **Win Rate:** {win_rate:.1f}% | **Avg R:** {avg_r:.2f}",
            "",
        ])

        # Categorical indicator win rates
        lines.extend([
            "## Categorical Indicator Win Rates",
            "",
            "Win rate for each state of categorical indicators at entry.",
            "",
        ])

        cat_indicators = [
            ('sma_config', 'SMA Configuration'),
            ('h1_structure', 'H1 Structure'),
            ('m15_structure', 'M15 Structure'),
            ('m5_structure', 'M5 Structure'),
            ('price_position', 'Price Position'),
            ('sma_momentum_label', 'SMA Momentum'),
        ]

        for col, name in cat_indicators:
            try:
                wr_df = self._provider.get_win_rate_by_state(trade_ids, col)
                if wr_df.empty:
                    continue

                lines.append(f"### {name}")
                lines.append("")
                lines.append("| State | Trades | Wins | Win Rate | Avg R |")
                lines.append("|-------|--------|------|----------|-------|")

                for _, row in wr_df.iterrows():
                    lines.append(
                        f"| {row['state']} | {int(row['trades'])} | "
                        f"{int(row['wins'])} | {row['win_rate']:.1f}% | "
                        f"{row['avg_r']:.2f} |"
                    )

                lines.append("")
            except Exception:
                pass

        # Continuous indicator quintile analysis
        lines.extend([
            "## Continuous Indicator Win Rates (by Quintile)",
            "",
            "Win rate for each quintile (20% bucket) of continuous indicators at entry.",
            "",
        ])

        cont_indicators = [
            ('candle_range_pct', 'Candle Range %'),
            ('vol_delta_roll', 'Volume Delta (5-bar)'),
            ('vol_roc', 'Volume ROC'),
            ('sma_spread_pct', 'SMA Spread %'),
            ('cvd_slope', 'CVD Slope'),
        ]

        for col, name in cont_indicators:
            try:
                q_df = self._provider.get_win_rate_by_quintile(trade_ids, col)
                if q_df.empty:
                    continue

                lines.append(f"### {name}")
                lines.append("")
                lines.append("| Quintile | Range Min | Range Max | Trades | Win Rate | Avg R |")
                lines.append("|----------|----------|----------|--------|----------|-------|")

                for _, row in q_df.iterrows():
                    lines.append(
                        f"| Q{int(row['quintile'])} | {row['range_min']:.4f} | "
                        f"{row['range_max']:.4f} | {int(row['trades'])} | "
                        f"{row['win_rate']:.1f}% | {row['avg_r']:.2f} |"
                    )

                lines.append("")
            except Exception:
                pass

        # Key observations for AI
        lines.extend([
            "## Key Observations for AI Analysis",
            "",
            "When analyzing entry snapshot data, consider:",
            "1. **Strongest categorical edges**: Which indicator states have the highest win rates with sufficient sample size?",
            "2. **Quintile sweet spots**: Are there clear 'golden zones' where win rate jumps?",
            "3. **Avoid zones**: Which states/quintiles should be avoided (low win rate + negative R)?",
            "4. **Direction asymmetry**: Do edges differ between LONG and SHORT trades?",
            "5. **Model differences**: Do different entry models (EPCH1-4) favor different indicator states?",
        ])

        (export_dir / "02_entry_snapshot.md").write_text("\n".join(lines), encoding="utf-8")

    # ==================================================================
    # 03_post_trade.md - Post-entry indicator behavior
    # ==================================================================
    def _export_post_trade(self, export_dir: Path, csv_dir: Path,
                           post_trade_avgs: pd.DataFrame, trade_ids: List[str]):
        # Save CSV
        if not post_trade_avgs.empty:
            post_trade_avgs.to_csv(csv_dir / "post_trade_averages.csv", index=False)

        lines = [
            "# 03 - Post-Trade Analysis: Indicator Behavior After Entry",
            "",
            f"Average indicator values across {POST_TRADE_BARS} M1 bars after entry.",
            "Bar 0 = entry candle. Direction-normalized: Vol Delta and CVD Slope are",
            "sign-flipped for SHORT trades so positive = favorable.",
            "",
        ]

        if post_trade_avgs.empty:
            lines.append("**No post-trade data available.**")
            (export_dir / "03_post_trade.md").write_text("\n".join(lines), encoding="utf-8")
            return

        # Early divergence analysis (first 5 bars)
        lines.extend([
            "## Early Divergence Analysis (First 5 Bars After Entry)",
            "",
            "How quickly do winners and losers diverge after entry?",
            "",
        ])

        first_5 = post_trade_avgs[post_trade_avgs['bar_sequence'] <= 5]
        if not first_5.empty:
            w_first5 = first_5[first_5['is_winner'] == True]
            l_first5 = first_5[first_5['is_winner'] == False]

            indicators = [
                ('avg_candle_range', 'Candle Range %'),
                ('avg_vol_delta', 'Vol Delta (normalized)'),
                ('avg_vol_roc', 'Vol ROC %'),
                ('avg_sma_spread', 'SMA Spread %'),
                ('avg_cvd_slope', 'CVD Slope (normalized)'),
            ]

            lines.append("| Indicator | Winner Avg (bars 0-5) | Loser Avg (bars 0-5) | Delta | Signal |")
            lines.append("|-----------|----------------------|---------------------|-------|--------|")

            for col, name in indicators:
                w_avg = w_first5[col].mean() if not w_first5.empty else 0
                l_avg = l_first5[col].mean() if not l_first5.empty else 0
                delta = w_avg - l_avg
                signal = "STRONG" if abs(delta) > abs(l_avg) * 0.1 else "WEAK"
                lines.append(
                    f"| {name} | {w_avg:.6f} | {l_avg:.6f} | "
                    f"{'+' if delta > 0 else ''}{delta:.6f} | {signal} |"
                )

            lines.append("")

        # Full bar-by-bar progression
        lines.extend([
            "## Full Bar-by-Bar Progression After Entry",
            "",
        ])

        for is_win, label in [(True, "Winners"), (False, "Losers")]:
            subset = post_trade_avgs[post_trade_avgs['is_winner'] == is_win]
            if subset.empty:
                continue

            lines.append(f"### {label}")
            lines.append("")
            lines.append("| Bar | Candle Range | Vol Delta | Vol ROC | SMA Spread | CVD Slope |")
            lines.append("|-----|-------------|-----------|---------|-----------|-----------|")

            for _, row in subset.iterrows():
                lines.append(
                    f"| {int(row['bar_sequence'])} | "
                    f"{row['avg_candle_range']:.6f} | "
                    f"{row['avg_vol_delta']:.6f} | "
                    f"{row['avg_vol_roc']:.4f} | "
                    f"{row['avg_sma_spread']:.6f} | "
                    f"{row['avg_cvd_slope']:.6f} |"
                )

            lines.append("")

        # Key observations for AI
        lines.extend([
            "## Key Observations for AI Analysis",
            "",
            "When analyzing post-trade data, consider:",
            "1. **Early exit signals**: At which bar do losers start diverging? Could this inform a trailing stop?",
            "2. **Confirmation window**: How many bars after entry before the trade is 'confirmed' as a winner?",
            "3. **Order flow persistence**: Does favorable CVD slope persist for winners or fade?",
            "4. **Volume signature**: Do winners show sustained volume or initial spike then fade?",
            "5. **Trade management**: Based on post-entry behavior, when should a trader move stop to breakeven?",
        ])

        (export_dir / "03_post_trade.md").write_text("\n".join(lines), encoding="utf-8")

    # ==================================================================
    # 04_deep_dive.md - Per-indicator three-phase analysis
    # ==================================================================
    def _export_deep_dive(self, export_dir: Path, csv_dir: Path,
                          entry_data: pd.DataFrame, trade_ids: List[str]):
        lines = [
            "# 04 - Indicator Deep Dive: Three-Phase Analysis",
            "",
            "Per-indicator breakdown across ramp-up (pre-entry), entry snapshot,",
            "and post-trade (post-entry) phases. Direction-normalized where applicable.",
            "",
        ]

        if not trade_ids:
            lines.append("**No trade data available.**")
            (export_dir / "04_deep_dive.md").write_text("\n".join(lines), encoding="utf-8")
            return

        # Three-phase analysis for each continuous indicator
        lines.append("## Three-Phase Progression (Continuous Indicators)")
        lines.append("")

        for col, name, ind_type in ALL_DEEP_DIVE_INDICATORS:
            if ind_type != 'continuous':
                continue

            lines.append(f"### {name}")

            # Normalization note for directional indicators
            if col in DataProvider.DIRECTIONAL_INDICATORS:
                lines.append(f"*Direction-normalized: positive = favorable for trade direction*")

            lines.append("")

            try:
                phase_df = self._provider.get_three_phase_averages(trade_ids, col)
                if phase_df.empty:
                    lines.append("No phase data available.")
                    lines.append("")
                    continue

                # Save CSV
                phase_df.to_csv(csv_dir / f"deep_dive_{col}.csv", index=False)

                # Ramp-up phase summary
                ramp = phase_df[phase_df['phase'] == 'ramp_up']
                post = phase_df[phase_df['phase'] == 'post_trade']

                for phase_name, phase_data, bar_label in [
                    ("Ramp-Up (pre-entry)", ramp, "bars -24 to -1"),
                    ("Post-Trade (post-entry)", post, "bars 0 to 24"),
                ]:
                    w_data = phase_data[phase_data['is_winner'] == True]
                    l_data = phase_data[phase_data['is_winner'] == False]

                    if w_data.empty and l_data.empty:
                        continue

                    w_avg = w_data['avg_value'].mean() if not w_data.empty else 0
                    l_avg = l_data['avg_value'].mean() if not l_data.empty else 0
                    delta = w_avg - l_avg

                    lines.append(
                        f"**{phase_name}** ({bar_label}): "
                        f"Winners avg={w_avg:.6f}, Losers avg={l_avg:.6f}, "
                        f"Delta={'+' if delta > 0 else ''}{delta:.6f}"
                    )

                lines.append("")
            except Exception as e:
                lines.append(f"Error: {e}")
                lines.append("")

        # Model x Direction breakdown for each indicator
        lines.extend([
            "## Model x Direction Breakdown",
            "",
            "Per-indicator win rate and average value by model and direction.",
            "",
        ])

        if not entry_data.empty:
            for col, name, ind_type in ALL_DEEP_DIVE_INDICATORS:
                if col not in entry_data.columns:
                    continue

                is_numeric = ind_type == 'continuous'
                val_header = "Avg Value" if is_numeric else "Most Common"

                lines.append(f"### {name}")
                lines.append("")
                lines.append(f"| Model | Direction | Trades | Win Rate | {val_header} |")
                lines.append("|-------|-----------|--------|----------|-----------|")

                for model in ['EPCH1', 'EPCH2', 'EPCH3', 'EPCH4']:
                    for direction in ['LONG', 'SHORT']:
                        subset = entry_data[
                            (entry_data['model'] == model) &
                            (entry_data['direction'] == direction)
                        ]
                        if len(subset) < 5:
                            continue

                        total = len(subset)
                        wr = subset['is_winner'].sum() / total * 100

                        if is_numeric:
                            avg_val = subset[col].mean()
                            val_str = f"{avg_val:.4f}"
                        else:
                            # For categorical: show mode (most common value)
                            val_str = str(subset[col].mode().iloc[0]) if not subset[col].mode().empty else "-"

                        lines.append(
                            f"| {model} | {direction} | {total} | "
                            f"{wr:.1f}% | {val_str} |"
                        )

                lines.append("")

        # Key observations for AI
        lines.extend([
            "## Key Observations for AI Analysis",
            "",
            "When analyzing deep dive data, consider:",
            "1. **Strongest predictor**: Which single indicator has the most consistent winner/loser separation across all phases?",
            "2. **Phase transitions**: Does any indicator 'flip' behavior between ramp-up and post-trade?",
            "3. **Model-specific edges**: Do some models benefit more from certain indicators?",
            "4. **Direction asymmetry**: After normalization, are LONGs and SHORTs equally predictable?",
            "5. **Leading indicators**: Which indicators diverge earliest in the ramp-up phase?",
        ])

        (export_dir / "04_deep_dive.md").write_text("\n".join(lines), encoding="utf-8")

    # ==================================================================
    # 05_composite_setup.md - Multi-indicator combination scoring
    # ==================================================================
    def _export_composite(self, export_dir: Path, csv_dir: Path,
                          entry_data: pd.DataFrame, trade_ids: List[str]):
        lines = [
            "# 05 - Composite Setup Analysis: Multi-Indicator Scoring",
            "",
            "Tests how indicators work together to identify ideal entry setups.",
            "Setup score is 0-7 based on favorable conditions present at entry.",
            "",
        ]

        if entry_data.empty:
            lines.append("**No entry data available.**")
            (export_dir / "05_composite_setup.md").write_text("\n".join(lines), encoding="utf-8")
            return

        # Calculate setup scores
        df = entry_data.copy()
        df['setup_score'] = 0

        scoring_rules = []

        if 'candle_range_pct' in df.columns:
            df['setup_score'] += (df['candle_range_pct'] >= 0.15).astype(int)
            scoring_rules.append("+1 if Candle Range >= 0.15%")

        if 'vol_roc' in df.columns:
            df['setup_score'] += (df['vol_roc'] >= 30).astype(int)
            scoring_rules.append("+1 if Vol ROC >= 30%")

        if 'sma_spread_pct' in df.columns:
            df['setup_score'] += (df['sma_spread_pct'] >= 0.15).astype(int)
            scoring_rules.append("+1 if SMA Spread >= 0.15%")

        if 'sma_config' in df.columns and 'direction' in df.columns:
            aligned = (
                ((df['direction'] == 'LONG') & (df['sma_config'] == 'BULL')) |
                ((df['direction'] == 'SHORT') & (df['sma_config'] == 'BEAR'))
            )
            df['setup_score'] += aligned.astype(int)
            scoring_rules.append("+1 if SMA Config aligned with direction (BULL/LONG or BEAR/SHORT)")

        if 'm5_structure' in df.columns and 'direction' in df.columns:
            m5_aligned = (
                ((df['direction'] == 'LONG') & (df['m5_structure'] == 'BULL')) |
                ((df['direction'] == 'SHORT') & (df['m5_structure'] == 'BEAR'))
            )
            df['setup_score'] += m5_aligned.astype(int)
            scoring_rules.append("+1 if M5 Structure aligned with direction")

        if 'h1_structure' in df.columns:
            df['setup_score'] += (df['h1_structure'] == 'NEUTRAL').astype(int)
            scoring_rules.append("+1 if H1 Structure is NEUTRAL")

        if 'cvd_slope' in df.columns and 'direction' in df.columns:
            cvd_aligned = (
                ((df['direction'] == 'LONG') & (df['cvd_slope'] > 0.1)) |
                ((df['direction'] == 'SHORT') & (df['cvd_slope'] < -0.1))
            )
            df['setup_score'] += cvd_aligned.astype(int)
            scoring_rules.append("+1 if CVD Slope aligned with direction (>0.1 for LONG, <-0.1 for SHORT)")

        # Scoring rules
        lines.append("## Setup Score Components (0-7)")
        lines.append("")
        for rule in scoring_rules:
            lines.append(f"- {rule}")
        lines.append("")

        # Score distribution
        lines.append("## Setup Score Distribution & Win Rate")
        lines.append("")

        score_groups = df.groupby('setup_score').agg(
            trades=('is_winner', 'count'),
            wins=('is_winner', 'sum'),
            avg_r=('pnl_r', 'mean'),
        ).reset_index()
        score_groups['win_rate'] = (score_groups['wins'] / score_groups['trades'] * 100).round(1)
        score_groups['avg_r'] = score_groups['avg_r'].round(2)

        lines.append("| Score | Trades | Wins | Win Rate | Avg R |")
        lines.append("|-------|--------|------|----------|-------|")

        for _, row in score_groups.iterrows():
            lines.append(
                f"| {int(row['setup_score'])} | {int(row['trades'])} | "
                f"{int(row['wins'])} | {row['win_rate']:.1f}% | {row['avg_r']:.2f} |"
            )

        lines.append("")

        # Save score CSV
        score_groups.to_csv(csv_dir / "setup_scores.csv", index=False)

        # Top/bottom combinations
        lines.extend([
            "## Indicator State Combinations",
            "",
            "Win rate for specific indicator state combinations (min 20 trades).",
            "",
        ])

        try:
            combo_df = self._provider.get_setup_combinations(trade_ids, min_trades=20)
            if not combo_df.empty:
                combo_df.to_csv(csv_dir / "setup_combinations.csv", index=False)

                lines.append("### Top 10 Combinations (Highest Win Rate)")
                lines.append("")
                lines.append("| SMA Config | H1 | M15 | Vol ROC | Candle | Trades | Win Rate | Avg R |")
                lines.append("|------------|-----|-----|---------|--------|--------|----------|-------|")

                for _, row in combo_df.head(10).iterrows():
                    lines.append(
                        f"| {row.get('sma_config', '-')} | "
                        f"{row.get('h1_structure', '-')} | "
                        f"{row.get('m15_structure', '-')} | "
                        f"{row.get('vol_roc_level', '-')} | "
                        f"{row.get('candle_level', '-')} | "
                        f"{int(row.get('trades', 0))} | "
                        f"{row.get('win_rate', 0):.1f}% | "
                        f"{row.get('avg_r', 0):.2f} |"
                    )

                lines.append("")

                if len(combo_df) > 10:
                    lines.append("### Bottom 10 Combinations (Lowest Win Rate)")
                    lines.append("")
                    lines.append("| SMA Config | H1 | M15 | Vol ROC | Candle | Trades | Win Rate | Avg R |")
                    lines.append("|------------|-----|-----|---------|--------|--------|----------|-------|")

                    for _, row in combo_df.tail(10).iterrows():
                        lines.append(
                            f"| {row.get('sma_config', '-')} | "
                            f"{row.get('h1_structure', '-')} | "
                            f"{row.get('m15_structure', '-')} | "
                            f"{row.get('vol_roc_level', '-')} | "
                            f"{row.get('candle_level', '-')} | "
                            f"{int(row.get('trades', 0))} | "
                            f"{row.get('win_rate', 0):.1f}% | "
                            f"{row.get('avg_r', 0):.2f} |"
                            )

                    lines.append("")
        except Exception:
            lines.append("*Error loading combination data.*")
            lines.append("")

        # Key observations for AI
        lines.extend([
            "## Key Observations for AI Analysis",
            "",
            "When analyzing composite setup data, consider:",
            "1. **Optimal score**: What setup score threshold gives the best risk-adjusted returns?",
            "2. **Diminishing returns**: Does win rate plateau after a certain score?",
            "3. **Required conditions**: Are there any must-have conditions regardless of score?",
            "4. **Avoid combinations**: Which specific combos should be filtered out entirely?",
            "5. **Actionable rules**: Propose 2-3 concrete pre-entry filter rules based on this data.",
        ])

        (export_dir / "05_composite_setup.md").write_text("\n".join(lines), encoding="utf-8")
