"""
Backtest Analytics and Reporting
Generates detailed performance reports and analysis
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional
import logging
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class BacktestAnalytics:
    """
    Analyzes backtest results and generates detailed reports
    """

    def __init__(self, results: Dict):
        """
        Initialize analytics with backtest results

        Args:
            results: Backtest results dict from BacktestEngine
        """
        self.results = results
        self.summary = results.get('summary', {})
        self.trades_stats = results.get('trades', {})
        self.signals = results.get('signals', {})
        self.equity_curve = results.get('equity_curve')
        self.closed_trades = results.get('closed_trades', [])

    def generate_report(self, save_path: Optional[str] = None) -> str:
        """
        Generate comprehensive text report

        Args:
            save_path: Optional path to save report

        Returns:
            Report as string
        """
        try:
            report_lines = []
            report_lines.append("="*80)
            report_lines.append("BACKTEST PERFORMANCE REPORT")
            report_lines.append("="*80)
            report_lines.append("")

            # Summary section
            report_lines.append("BACKTEST SUMMARY")
            report_lines.append("-"*80)
            report_lines.append(f"Period: {self.summary.get('start_date', 'N/A').date()} to {self.summary.get('end_date', 'N/A').date()}")
            report_lines.append(f"Duration: {self.summary.get('duration_days', 0)} days")
            report_lines.append(f"Initial Balance: ${self.summary.get('initial_balance', 0):,.2f}")
            report_lines.append(f"Final Balance: ${self.summary.get('final_balance', 0):,.2f}")
            report_lines.append(f"Final Equity: ${self.summary.get('final_equity', 0):,.2f}")
            report_lines.append(f"Net Profit: ${self.summary.get('net_profit', 0):,.2f}")
            report_lines.append(f"Return: {self.summary.get('return_pct', 0):.2f}%")
            report_lines.append("")

            # Risk metrics
            report_lines.append("RISK METRICS")
            report_lines.append("-"*80)
            report_lines.append(f"Maximum Drawdown: {self.summary.get('max_drawdown_pct', 0):.2f}%")
            report_lines.append(f"Max DD Duration: {self.summary.get('max_drawdown_duration_days', 0)} days")
            report_lines.append(f"Sharpe Ratio: {self.summary.get('sharpe_ratio', 0):.2f}")
            report_lines.append("")

            # Trading statistics
            report_lines.append("TRADING STATISTICS")
            report_lines.append("-"*80)
            report_lines.append(f"Total Trades: {self.trades_stats.get('total', 0)}")
            report_lines.append(f"Winning Trades: {self.trades_stats.get('wins', 0)}")
            report_lines.append(f"Losing Trades: {self.trades_stats.get('losses', 0)}")
            report_lines.append(f"Win Rate: {self.trades_stats.get('win_rate_pct', 0):.2f}%")
            report_lines.append(f"Average Win: ${self.trades_stats.get('avg_win', 0):.2f}")
            report_lines.append(f"Average Loss: ${self.trades_stats.get('avg_loss', 0):.2f}")
            report_lines.append(f"Largest Win: ${self.trades_stats.get('largest_win', 0):.2f}")
            report_lines.append(f"Largest Loss: ${self.trades_stats.get('largest_loss', 0):.2f}")
            report_lines.append(f"Profit Factor: {self.trades_stats.get('profit_factor', 0):.2f}")
            report_lines.append("")

            # Signal statistics
            report_lines.append("SIGNAL STATISTICS")
            report_lines.append("-"*80)
            report_lines.append(f"Signals Generated: {self.signals.get('total_generated', 0)}")
            report_lines.append(f"Signals Executed: {self.signals.get('total_executed', 0)}")
            report_lines.append(f"Execution Rate: {self.signals.get('execution_rate_pct', 0):.2f}%")
            report_lines.append("")

            # Trade distribution
            if self.closed_trades:
                report_lines.append("TRADE DISTRIBUTION")
                report_lines.append("-"*80)
                profits = [t['profit'] for t in self.closed_trades]
                report_lines.append(f"Median P&L: ${np.median(profits):.2f}")
                report_lines.append(f"Std Dev P&L: ${np.std(profits):.2f}")
                report_lines.append(f"Best Day: ${max(profits):.2f}")
                report_lines.append(f"Worst Day: ${min(profits):.2f}")
                report_lines.append("")

            # Monthly performance
            if self.closed_trades:
                monthly_perf = self._calculate_monthly_performance()
                if monthly_perf:
                    report_lines.append("MONTHLY PERFORMANCE")
                    report_lines.append("-"*80)
                    for month, profit in monthly_perf.items():
                        report_lines.append(f"{month}: ${profit:.2f}")
                    report_lines.append("")

            # Rating
            rating = self._calculate_strategy_rating()
            report_lines.append("STRATEGY RATING")
            report_lines.append("-"*80)
            report_lines.append(f"Overall Score: {rating['score']:.1f}/100")
            report_lines.append(f"Grade: {rating['grade']}")
            report_lines.append("")
            report_lines.append("Rating Breakdown:")
            for criterion, score in rating['breakdown'].items():
                report_lines.append(f"  {criterion}: {score:.1f}/20")
            report_lines.append("")

            # Recommendations
            recommendations = self._generate_recommendations()
            if recommendations:
                report_lines.append("RECOMMENDATIONS")
                report_lines.append("-"*80)
                for i, rec in enumerate(recommendations, 1):
                    report_lines.append(f"{i}. {rec}")
                report_lines.append("")

            report_lines.append("="*80)
            report_lines.append(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report_lines.append("="*80)

            report = "\n".join(report_lines)

            # Save if path provided
            if save_path:
                Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                with open(save_path, 'w') as f:
                    f.write(report)
                logger.info(f"Report saved to {save_path}")

            return report

        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return ""

    def _calculate_monthly_performance(self) -> Dict[str, float]:
        """Calculate monthly profit/loss"""
        try:
            if not self.closed_trades:
                return {}

            monthly = {}
            for trade in self.closed_trades:
                month_key = trade['time_close'].strftime('%Y-%m')
                if month_key not in monthly:
                    monthly[month_key] = 0.0
                monthly[month_key] += trade['profit']

            return monthly

        except Exception as e:
            logger.error(f"Error calculating monthly performance: {e}")
            return {}

    def _calculate_strategy_rating(self) -> Dict:
        """
        Calculate overall strategy rating (0-100)

        Breakdown:
        - Profitability (20 pts)
        - Win Rate (20 pts)
        - Profit Factor (20 pts)
        - Risk Management (20 pts)
        - Consistency (20 pts)
        """
        try:
            scores = {}

            # Profitability (20 pts) - based on return %
            return_pct = self.summary.get('return_pct', 0)
            if return_pct >= 100:
                scores['Profitability'] = 20
            elif return_pct >= 50:
                scores['Profitability'] = 15
            elif return_pct >= 20:
                scores['Profitability'] = 10
            elif return_pct >= 0:
                scores['Profitability'] = 5
            else:
                scores['Profitability'] = 0

            # Win Rate (20 pts)
            win_rate = self.trades_stats.get('win_rate_pct', 0)
            if win_rate >= 70:
                scores['Win Rate'] = 20
            elif win_rate >= 60:
                scores['Win Rate'] = 15
            elif win_rate >= 50:
                scores['Win Rate'] = 10
            elif win_rate >= 40:
                scores['Win Rate'] = 5
            else:
                scores['Win Rate'] = 0

            # Profit Factor (20 pts)
            pf = self.trades_stats.get('profit_factor', 0)
            if pf >= 3.0:
                scores['Profit Factor'] = 20
            elif pf >= 2.0:
                scores['Profit Factor'] = 15
            elif pf >= 1.5:
                scores['Profit Factor'] = 10
            elif pf >= 1.0:
                scores['Profit Factor'] = 5
            else:
                scores['Profit Factor'] = 0

            # Risk Management (20 pts) - based on max drawdown
            max_dd = abs(self.summary.get('max_drawdown_pct', 0))
            if max_dd <= 5:
                scores['Risk Management'] = 20
            elif max_dd <= 10:
                scores['Risk Management'] = 15
            elif max_dd <= 20:
                scores['Risk Management'] = 10
            elif max_dd <= 30:
                scores['Risk Management'] = 5
            else:
                scores['Risk Management'] = 0

            # Consistency (20 pts) - based on Sharpe ratio
            sharpe = self.summary.get('sharpe_ratio', 0)
            if sharpe >= 2.0:
                scores['Consistency'] = 20
            elif sharpe >= 1.5:
                scores['Consistency'] = 15
            elif sharpe >= 1.0:
                scores['Consistency'] = 10
            elif sharpe >= 0.5:
                scores['Consistency'] = 5
            else:
                scores['Consistency'] = 0

            total_score = sum(scores.values())

            # Determine grade
            if total_score >= 90:
                grade = 'A+'
            elif total_score >= 80:
                grade = 'A'
            elif total_score >= 70:
                grade = 'B'
            elif total_score >= 60:
                grade = 'C'
            elif total_score >= 50:
                grade = 'D'
            else:
                grade = 'F'

            return {
                'score': total_score,
                'grade': grade,
                'breakdown': scores
            }

        except Exception as e:
            logger.error(f"Error calculating rating: {e}")
            return {'score': 0, 'grade': 'F', 'breakdown': {}}

    def _generate_recommendations(self) -> List[str]:
        """Generate actionable recommendations based on results"""
        recommendations = []

        try:
            # Low win rate
            if self.trades_stats.get('win_rate_pct', 0) < 50:
                recommendations.append(
                    "Win rate is below 50%. Consider increasing signal quality filters or "
                    "adjusting entry criteria."
                )

            # High drawdown
            if abs(self.summary.get('max_drawdown_pct', 0)) > 20:
                recommendations.append(
                    "Maximum drawdown exceeds 20%. Consider reducing position sizes or "
                    "implementing tighter stop losses."
                )

            # Low profit factor
            if self.trades_stats.get('profit_factor', 0) < 1.5:
                recommendations.append(
                    "Profit factor is below 1.5. Review risk:reward ratios and consider "
                    "targeting larger wins or cutting losses earlier."
                )

            # Too many trades
            total_trades = self.trades_stats.get('total', 0)
            duration_days = self.summary.get('duration_days', 1)
            trades_per_day = total_trades / duration_days if duration_days > 0 else 0

            if trades_per_day > 5:
                recommendations.append(
                    "High trading frequency detected. Consider being more selective with "
                    "signals to reduce commission costs."
                )

            # Too few trades
            if trades_per_day < 0.1:
                recommendations.append(
                    "Very low trading frequency. Consider adjusting filters to capture "
                    "more opportunities or reducing minimum signal score."
                )

            # Good performance
            if self.summary.get('return_pct', 0) > 50 and abs(self.summary.get('max_drawdown_pct', 0)) < 15:
                recommendations.append(
                    "Excellent performance! Strategy shows strong profitability with controlled risk. "
                    "Consider testing on live demo account."
                )

            # Negative returns
            if self.summary.get('return_pct', 0) < 0:
                recommendations.append(
                    "Strategy shows negative returns. Major adjustments needed. Review "
                    "all parameters and consider different market conditions."
                )

        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")

        return recommendations

    def save_results_json(self, filepath: str):
        """Save results as JSON"""
        try:
            # Convert datetime objects to strings
            results_copy = self.results.copy()

            # Convert summary dates
            if 'summary' in results_copy:
                for key in ['start_date', 'end_date']:
                    if key in results_copy['summary'] and isinstance(results_copy['summary'][key], datetime):
                        results_copy['summary'][key] = results_copy['summary'][key].isoformat()

            # Remove equity curve (too large for JSON)
            if 'equity_curve' in results_copy:
                del results_copy['equity_curve']

            # Convert trade times
            if 'closed_trades' in results_copy:
                for trade in results_copy['closed_trades']:
                    for key in ['time_open', 'time_close']:
                        if key in trade and isinstance(trade[key], datetime):
                            trade[key] = trade[key].isoformat()

            # Save
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, 'w') as f:
                json.dump(results_copy, f, indent=2)

            logger.info(f"Results saved to {filepath}")

        except Exception as e:
            logger.error(f"Error saving results JSON: {e}")

    def save_equity_curve_csv(self, filepath: str):
        """Save equity curve as CSV"""
        try:
            if self.equity_curve is not None:
                self.equity_curve.to_csv(filepath)
                logger.info(f"Equity curve saved to {filepath}")
            else:
                logger.warning("No equity curve to save")

        except Exception as e:
            logger.error(f"Error saving equity curve: {e}")

    def save_trades_csv(self, filepath: str):
        """Save closed trades as CSV"""
        try:
            if self.closed_trades:
                df = pd.DataFrame(self.closed_trades)
                df.to_csv(filepath, index=False)
                logger.info(f"Trades saved to {filepath}")
            else:
                logger.warning("No trades to save")

        except Exception as e:
            logger.error(f"Error saving trades: {e}")
