"""
Small Capital Optimization Module
Specialized strategies and risk management for accounts under $2000

This module implements proven strategies for growing small trading accounts
while maintaining strict risk management to preserve capital.
"""

import logging
from typing import Dict, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class SmallCapitalOptimizer:
    """
    Optimizes trading for small capital accounts (<$2000)

    Key Principles:
    1. Capital Preservation First - protect every dollar
    2. Quality Over Quantity - only highest probability setups
    3. Compound Gains - reinvest profits for exponential growth
    4. Adaptive Risk - adjust to account performance
    5. Fast Protection - quick break-even and profit taking
    """

    def __init__(self, config: Dict):
        self.config = config
        self.account_tier = None
        self.optimized_params = {}

    def get_account_tier(self, balance: float) -> str:
        """
        Classify account into tiers for different strategies

        Returns:
            micro: $0-$500
            small: $500-$1000
            medium: $1000-$2000
            standard: >$2000
        """
        if balance < 500:
            return 'micro'
        elif balance < 1000:
            return 'small'
        elif balance < 2000:
            return 'medium'
        else:
            return 'standard'

    def get_optimized_risk(self, balance: float, consecutive_losses: int = 0,
                          win_rate: float = 0.0) -> float:
        """
        Calculate optimized risk percentage for account size

        Args:
            balance: Current account balance
            consecutive_losses: Number of consecutive losses
            win_rate: Current win rate (0-100)

        Returns:
            Optimized risk percentage per trade
        """
        try:
            tier = self.get_account_tier(balance)

            # Base risk by tier
            base_risk = {
                'micro': 0.3,    # Ultra conservative
                'small': 0.5,    # Conservative
                'medium': 0.7,   # Moderate
                'standard': 1.0  # Standard
            }

            risk_pct = base_risk.get(tier, 0.5)

            # Adjust for consecutive losses
            if consecutive_losses >= 2:
                risk_pct *= 0.5  # Halve risk after 2 losses
                logger.info(f"Risk reduced to {risk_pct}% due to {consecutive_losses} consecutive losses")
            elif consecutive_losses >= 1:
                risk_pct *= 0.75  # Reduce risk by 25% after 1 loss

            # Adjust based on win rate (if we have enough trades)
            if win_rate > 0:
                if win_rate >= 70:
                    risk_pct *= 1.2  # Increase risk slightly on hot streak
                    risk_pct = min(risk_pct, 1.0)  # Cap at 1%
                elif win_rate < 50:
                    risk_pct *= 0.8  # Reduce risk if struggling

            # Never exceed these limits for small accounts
            if tier == 'micro':
                risk_pct = min(risk_pct, 0.5)  # Max 0.5% for micro accounts
            elif tier == 'small':
                risk_pct = min(risk_pct, 0.7)  # Max 0.7% for small accounts

            logger.info(f"Optimized risk for {tier} account (${balance:.2f}): {risk_pct}%")

            return risk_pct

        except Exception as e:
            logger.error(f"Error calculating optimized risk: {e}")
            return 0.3  # Safe fallback

    def should_take_signal(self, signal: Dict, balance: float,
                          daily_trades: int = 0) -> Tuple[bool, str]:
        """
        Determine if signal meets small capital criteria

        Returns:
            (should_take, reason)
        """
        try:
            tier = self.get_account_tier(balance)

            # Minimum signal score requirements by tier
            min_scores = {
                'micro': 5,      # Only the best for micro accounts
                'small': 7,      # High quality for small accounts
                'medium': 6,     # Good quality for medium accounts
                'standard': 5    # Standard threshold
            }

            min_score = min_scores.get(tier, 7)
            signal_score = signal.get('signal_score', 0)

            if signal_score < min_score:
                return False, f"Signal score {signal_score} below threshold {min_score} for {tier} account"

            # Limit daily trades for small accounts
            max_daily_trades = {
                'micro': 100,      # Max 2 trades/day for micro
                'small': 3,      # Max 3 trades/day for small
                'medium': 5,     # Max 5 trades/day for medium
                'standard': 10   # Standard limit
            }

            max_trades = max_daily_trades.get(tier, 3)
            if daily_trades >= max_trades:
                return False, f"Daily trade limit reached ({daily_trades}/{max_trades}) for {tier} account"

            # Require higher R:R for small accounts
            min_rr = {
                'micro': 1.5,    # Need 2.5:1 minimum for micro
                'small': 2.0,    # Need 2:1 for small
                'medium': 1.8,   # Need 1.8:1 for medium
                'standard': 1.5  # Standard 1.5:1
            }

            required_rr = min_rr.get(tier, 2.0)
            signal_rr = signal.get('rr_ratio', 0)

            if signal_rr < required_rr:
                return False, f"R:R {signal_rr:.2f} below threshold {required_rr} for {tier} account"

            # For micro accounts, ONLY trade during kill zones
            if tier == 'micro':
                is_killzone = signal.get('in_killzone', False)
                if not is_killzone:
                    pass
                    #return False, "Micro accounts should only trade during kill zones"

            # Check ML confidence for small accounts
            #ml_confidence = signal.get('ml_confidence', 0)
            #if tier in ['micro', 'small'] and ml_confidence < 0.65:
             #   return False, f"ML confidence {ml_confidence:.2%} too low for {tier} account"

            return True, "Signal meets small capital criteria"

        except Exception as e:
            logger.error(f"Error checking signal for small capital: {e}")
            return False, f"Error: {e}"

    def get_position_management_params(self, balance: float) -> Dict:
        """
        Get optimized position management parameters for account size
        """
        try:
            tier = self.get_account_tier(balance)

            # Tighter management for smaller accounts
            params = {
                'micro': {
                    'break_even_activation': 0.3,  # Move to BE at 0.3% profit
                    'break_even_buffer': 0.05,     # Small buffer
                    'trailing_activation': 0.7,     # Start trailing at 0.7%
                    'trailing_distance': 0.25,      # Tight trailing
                    'partial_profits': [
                        {'pct': 0.5, 'close_pct': 40},   # Take 40% at 0.5%
                        {'pct': 1.0, 'close_pct': 30},   # Take 30% at 1.0%
                        {'pct': 1.5, 'close_pct': 30},   # Take 30% at 1.5%
                    ],
                    'max_hold_hours': 12,  # Shorter hold time
                },
                'small': {
                    'break_even_activation': 0.4,
                    'break_even_buffer': 0.08,
                    'trailing_activation': 0.8,
                    'trailing_distance': 0.3,
                    'partial_profits': [
                        {'pct': 0.7, 'close_pct': 30},
                        {'pct': 1.2, 'close_pct': 30},
                        {'pct': 2.0, 'close_pct': 40},
                    ],
                    'max_hold_hours': 18,
                },
                'medium': {
                    'break_even_activation': 0.5,
                    'break_even_buffer': 0.1,
                    'trailing_activation': 1.0,
                    'trailing_distance': 0.4,
                    'partial_profits': [
                        {'pct': 1.0, 'close_pct': 30},
                        {'pct': 2.0, 'close_pct': 30},
                        {'pct': 3.0, 'close_pct': 40},
                    ],
                    'max_hold_hours': 24,
                },
                'standard': {
                    'break_even_activation': 0.5,
                    'break_even_buffer': 0.1,
                    'trailing_activation': 1.0,
                    'trailing_distance': 0.5,
                    'partial_profits': [
                        {'pct': 1.0, 'close_pct': 30},
                        {'pct': 2.0, 'close_pct': 30},
                        {'pct': 3.0, 'close_pct': 40},
                    ],
                    'max_hold_hours': 24,
                }
            }

            return params.get(tier, params['standard'])

        except Exception as e:
            logger.error(f"Error getting position management params: {e}")
            return {}

    def get_loss_limits(self, balance: float) -> Dict:
        """
        Get daily/weekly loss limits optimized for account size
        """
        try:
            tier = self.get_account_tier(balance)

            # Tighter limits for smaller accounts
            limits = {
                'micro': {
                    'daily': 1.5,    # Max 1.5% daily loss
                    'weekly': 3.0,   # Max 3% weekly loss
                    'monthly': 8.0,  # Max 8% monthly loss
                },
                'small': {
                    'daily': 2.0,
                    'weekly': 5.0,
                    'monthly': 10.0,
                },
                'medium': {
                    'daily': 3.0,
                    'weekly': 7.0,
                    'monthly': 12.0,
                },
                'standard': {
                    'daily': 5.0,
                    'weekly': 10.0,
                    'monthly': 15.0,
                }
            }

            return limits.get(tier, limits['small'])

        except Exception as e:
            logger.error(f"Error getting loss limits: {e}")
            return {'daily': 2.0, 'weekly': 5.0, 'monthly': 10.0}

    def get_recommended_symbols(self, balance: float) -> list:
        """
        Get recommended symbols for account size
        """
        try:
            tier = self.get_account_tier(balance)

            # Smaller accounts should focus on fewer, more liquid pairs
            recommendations = {
                'micro': ['BTCUSDm'],  # Only BTC for micro
                'small': ['BTCUSD', 'ETHUSD'],  # BTC + ETH for small
                'medium': ['BTCUSD', 'ETHUSD', 'SOLUSD'],  # Top 3 for medium
                'standard': ['BTCUSD', 'ETHUSD', 'SOLUSD', 'AVAXUSD', 'MATICUSD']  # All pairs
            }

            return recommendations.get(tier, recommendations['small'])

        except Exception as e:
            logger.error(f"Error getting recommended symbols: {e}")
            return ['BTCUSD']

    def get_growth_strategy(self, balance: float, starting_balance: float) -> Dict:
        """
        Get growth strategy recommendations based on account progress
        """
        try:
            tier = self.get_account_tier(balance)
            growth_pct = ((balance - starting_balance) / starting_balance * 100) if starting_balance > 0 else 0

            strategy = {
                'current_tier': tier,
                'balance': balance,
                'starting_balance': starting_balance,
                'growth_pct': growth_pct,
                'recommendations': []
            }

            # Growth milestones and recommendations
            if tier == 'micro':
                strategy['next_milestone'] = 500
                strategy['recommendations'] = [
                    "Focus on quality over quantity - max 2 trades/day",
                    "Only trade during kill zones (London/NY)",
                    "Require signal score >= 8/10",
                    "Take partial profits early (at 0.5% gain)",
                    "Move to break-even quickly (at 0.3% profit)",
                ]
                if growth_pct >= 20:
                    strategy['recommendations'].append(
                        "Excellent progress! Consider withdrawing 10% as security"
                    )

            elif tier == 'small':
                strategy['next_milestone'] = 1000
                strategy['recommendations'] = [
                    "Maintain discipline - max 3 trades/day",
                    "Require signal score >= 7/10",
                    "Focus on BTC and ETH only",
                    "Take partial profits at 0.7%, 1.2%, 2.0%",
                ]
                if growth_pct >= 30:
                    strategy['recommendations'].append(
                        "Great work! Consider securing profits periodically"
                    )

            elif tier == 'medium':
                strategy['next_milestone'] = 2000
                strategy['recommendations'] = [
                    "You can trade up to 5 times/day",
                    "Signal score >= 6/10 acceptable",
                    "Can trade BTC, ETH, SOL",
                    "Standard position management applies",
                ]

            else:  # standard
                strategy['next_milestone'] = balance * 1.5  # Next 50% growth
                strategy['recommendations'] = [
                    "Standard risk management applies",
                    "All symbols available",
                    "Can use full advanced features",
                    "Consider diversification strategies",
                ]

            return strategy

        except Exception as e:
            logger.error(f"Error getting growth strategy: {e}")
            return {}

    def should_halt_trading(self, balance: float, starting_balance: float,
                           consecutive_losses: int) -> Tuple[bool, str]:
        """
        Determine if trading should be halted for the day/week
        """
        try:
            tier = self.get_account_tier(balance)
            limits = self.get_loss_limits(balance)

            # Check daily loss
            daily_loss_pct = ((starting_balance - balance) / starting_balance * 100) if starting_balance > 0 else 0

            if daily_loss_pct >= limits['daily']:
                return True, f"Daily loss limit reached: {daily_loss_pct:.2f}% (limit: {limits['daily']}%)"

            # Halt on consecutive losses for small accounts
            max_consecutive = 2 if tier in ['micro', 'small'] else 3

            if consecutive_losses >= max_consecutive:
                return True, f"Too many consecutive losses: {consecutive_losses} (limit: {max_consecutive})"

            # Additional safeguard for micro accounts
            if tier == 'micro' and balance < starting_balance * 0.95:
                return True, "Micro account lost 5% - halting to preserve capital"

            return False, "Trading can continue"

        except Exception as e:
            logger.error(f"Error checking halt condition: {e}")
            return True, f"Error occurred - halting for safety: {e}"
