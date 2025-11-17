"""
Advanced Risk Management Module
Implements hedge fund-grade risk management with Kelly Criterion, portfolio-level risk,
and adaptive position sizing
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class RiskMetrics:
    """Portfolio risk metrics"""
    total_exposure: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    expectancy: float
    kelly_percentage: float


@dataclass
class PositionRisk:
    """Risk calculation for a single position"""
    symbol: str
    entry_price: float
    stop_loss: float
    position_size: float
    risk_amount: float
    risk_percentage: float
    reward_risk_ratio: float
    kelly_fraction: float


class AdvancedRiskManager:
    """
    Professional hedge fund-grade risk management
    - Kelly Criterion for optimal position sizing
    - Portfolio-level risk management
    - Adaptive risk based on market conditions
    - Maximum drawdown protection
    - Time-based exposure limits
    """

    def __init__(self, config: Dict):
        """Initialize advanced risk manager"""
        self.config = config

        # Risk parameters
        self.base_risk_pct = config.get('risk_pct_per_trade', 0.5)
        self.max_daily_loss_pct = config.get('max_daily_loss_pct', 5.0)
        self.max_weekly_loss_pct = config.get('max_weekly_loss_pct', 10.0)
        self.max_monthly_loss_pct = config.get('max_monthly_loss_pct', 15.0)
        self.max_portfolio_exposure = config.get('max_portfolio_exposure', 10.0)
        self.max_single_position_pct = config.get('max_single_position_pct', 2.0)
        self.max_correlated_exposure = config.get('max_correlated_exposure', 5.0)

        # Kelly Criterion parameters
        self.kelly_fraction = config.get('kelly_fraction', 0.25)  # Use 25% of full Kelly
        self.min_trades_for_kelly = config.get('min_trades_for_kelly', 20)

        # Adaptive risk parameters
        self.volatility_lookback = config.get('volatility_lookback', 20)
        self.risk_scaling_factor = config.get('risk_scaling_factor', 1.0)

        # State tracking
        self.daily_pnl = 0.0
        self.weekly_pnl = 0.0
        self.monthly_pnl = 0.0
        self.peak_balance = 0.0
        self.daily_reset_time = None
        self.weekly_reset_time = None
        self.monthly_reset_time = None

        # Trade history for statistics
        self.trade_history: List[Dict] = []
        self.recent_losses = 0

        logger.info("Advanced Risk Manager initialized")

    def calculate_kelly_criterion(self, win_rate: float, avg_win: float,
                                  avg_loss: float) -> float:
        """
        Calculate Kelly Criterion percentage
        Kelly% = (Win% * Avg Win - Loss% * Avg Loss) / Avg Win

        Returns optimal position size as percentage of capital
        """
        try:
            if win_rate <= 0 or win_rate >= 1 or avg_win <= 0 or avg_loss <= 0:
                return 0.0

            loss_rate = 1 - win_rate

            # Kelly formula
            kelly_pct = (win_rate * avg_win - loss_rate * avg_loss) / avg_win

            # Apply fractional Kelly (more conservative)
            fractional_kelly = kelly_pct * self.kelly_fraction

            # Cap at reasonable limits
            return max(0.0, min(fractional_kelly, 0.05))  # Max 5% per trade

        except Exception as e:
            logger.error(f"Error calculating Kelly Criterion: {e}")
            return 0.0

    def calculate_position_size(self, symbol: str, entry_price: float,
                               stop_loss: float, account_balance: float,
                               current_volatility: float = 1.0,
                               win_rate: Optional[float] = None,
                               avg_win: Optional[float] = None,
                               avg_loss: Optional[float] = None) -> PositionRisk:
        """
        Calculate optimal position size using multiple methods
        Combines Kelly Criterion with volatility-adjusted sizing
        """
        try:
            # Safety check for account balance
            if account_balance <= 0:
                logger.error(f"Invalid account balance: {account_balance}")
                return None

            # Calculate base risk amount
            base_risk_amount = account_balance * (self.base_risk_pct / 100)

            # Adjust for current volatility (reduce size in high volatility)
            volatility_adjustment = 1.0 / max(current_volatility, 0.5)
            volatility_adjustment = min(volatility_adjustment, 2.0)  # Cap adjustment

            # Calculate Kelly-based sizing if we have enough trade history
            kelly_pct = 0.0
            if win_rate and avg_win and avg_loss and len(self.trade_history) >= self.min_trades_for_kelly:
                kelly_pct = self.calculate_kelly_criterion(win_rate, avg_win, avg_loss)

            # Use Kelly if available, otherwise use base risk
            if kelly_pct > 0:
                risk_amount = account_balance * kelly_pct * volatility_adjustment
            else:
                risk_amount = base_risk_amount * volatility_adjustment

            # Apply risk scaling based on recent performance
            risk_amount *= self.risk_scaling_factor

            # Calculate position size based on stop loss distance
            risk_per_unit = abs(entry_price - stop_loss)
            if risk_per_unit == 0:
                logger.error("Stop loss equals entry price")
                return None

            position_size = risk_amount / risk_per_unit

            # Validate position size
            max_position_value = account_balance * (self.max_single_position_pct / 100)
            position_value = position_size * entry_price

            if position_value > max_position_value:
                position_size = max_position_value / entry_price
                risk_amount = position_size * risk_per_unit

            risk_percentage = (risk_amount / account_balance) * 100

            # Calculate reward:risk ratio (assume TP is 2x risk)
            take_profit_distance = abs(entry_price - stop_loss) * 2
            reward_risk_ratio = take_profit_distance / abs(entry_price - stop_loss)

            return PositionRisk(
                symbol=symbol,
                entry_price=entry_price,
                stop_loss=stop_loss,
                position_size=position_size,
                risk_amount=risk_amount,
                risk_percentage=risk_percentage,
                reward_risk_ratio=reward_risk_ratio,
                kelly_fraction=kelly_pct
            )

        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return None

    def can_take_trade(self, account_balance: float, current_exposure: float,
                      new_position_risk: float) -> Tuple[bool, str]:
        """
        Determine if a new trade can be taken based on risk limits
        Returns (can_trade, reason)
        """
        try:
            # Safety check
            if account_balance <= 0:
                return False, f"Invalid account balance: {account_balance}"

            # Check daily loss limit
            daily_loss_pct = (abs(self.daily_pnl) / account_balance) * 100
            if self.daily_pnl < 0 and daily_loss_pct >= self.max_daily_loss_pct:
                return False, f"Daily loss limit reached: {daily_loss_pct:.2f}%"

            # Check weekly loss limit
            weekly_loss_pct = (abs(self.weekly_pnl) / account_balance) * 100
            if self.weekly_pnl < 0 and weekly_loss_pct >= self.max_weekly_loss_pct:
                return False, f"Weekly loss limit reached: {weekly_loss_pct:.2f}%"

            # Check monthly loss limit
            monthly_loss_pct = (abs(self.monthly_pnl) / account_balance) * 100
            if self.monthly_pnl < 0 and monthly_loss_pct >= self.max_monthly_loss_pct:
                return False, f"Monthly loss limit reached: {monthly_loss_pct:.2f}%"

            # Check portfolio exposure
            total_exposure_pct = ((current_exposure + new_position_risk) / account_balance) * 100
            if total_exposure_pct > self.max_portfolio_exposure:
                return False, f"Portfolio exposure limit exceeded: {total_exposure_pct:.2f}%"

            # Check consecutive losses
            if self.recent_losses >= 3:
                return False, f"Too many consecutive losses: {self.recent_losses}"

            # Check if risk scaling is too low (indicating poor recent performance)
            if self.risk_scaling_factor < 0.3:
                return False, f"Risk scaled down due to poor performance: {self.risk_scaling_factor:.2f}"

            return True, "OK"

        except Exception as e:
            logger.error(f"Error checking trade eligibility: {e}")
            return False, f"Error: {str(e)}"

    def update_pnl(self, profit: float, is_win: bool):
        """Update PnL tracking and risk scaling"""
        try:
            self.daily_pnl += profit
            self.weekly_pnl += profit
            self.monthly_pnl += profit

            # Update consecutive losses
            if is_win:
                self.recent_losses = 0
            else:
                self.recent_losses += 1

            # Adjust risk scaling based on recent performance
            if is_win:
                # Slightly increase risk after wins (max 1.5x)
                self.risk_scaling_factor = min(self.risk_scaling_factor * 1.05, 1.5)
            else:
                # Reduce risk after losses (min 0.3x)
                self.risk_scaling_factor = max(self.risk_scaling_factor * 0.9, 0.3)

        except Exception as e:
            logger.error(f"Error updating PnL: {e}")

    def reset_daily_limits(self, current_balance: float):
        """Reset daily tracking"""
        self.daily_pnl = 0.0
        self.daily_reset_time = datetime.utcnow()

        # Update peak balance for drawdown calculation
        if current_balance > self.peak_balance:
            self.peak_balance = current_balance

    def reset_weekly_limits(self):
        """Reset weekly tracking"""
        self.weekly_pnl = 0.0
        self.weekly_reset_time = datetime.utcnow()

    def reset_monthly_limits(self):
        """Reset monthly tracking"""
        self.monthly_pnl = 0.0
        self.monthly_reset_time = datetime.utcnow()

    def add_trade_to_history(self, trade: Dict):
        """Add completed trade to history for statistics"""
        try:
            self.trade_history.append({
                'timestamp': datetime.utcnow(),
                'symbol': trade.get('symbol'),
                'profit': trade.get('profit', 0),
                'is_win': trade.get('profit', 0) > 0,
                'risk_amount': trade.get('risk_amount', 0),
                'rr_ratio': trade.get('rr_ratio', 0),
            })

            # Keep only recent history (last 100 trades)
            if len(self.trade_history) > 100:
                self.trade_history = self.trade_history[-100:]

        except Exception as e:
            logger.error(f"Error adding trade to history: {e}")

    def calculate_portfolio_metrics(self, account_balance: float) -> RiskMetrics:
        """Calculate comprehensive portfolio risk metrics"""
        try:
            if len(self.trade_history) < 2:
                return RiskMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

            # Safety check
            if account_balance <= 0:
                logger.warning(f"Invalid account balance for metrics: {account_balance}")
                return RiskMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

            # Calculate statistics
            wins = [t for t in self.trade_history if t['is_win']]
            losses = [t for t in self.trade_history if not t['is_win']]

            win_rate = len(wins) / len(self.trade_history) if self.trade_history else 0
            avg_win = np.mean([t['profit'] for t in wins]) if wins else 0
            avg_loss = abs(np.mean([t['profit'] for t in losses])) if losses else 0

            # Total exposure
            total_exposure = sum([t['risk_amount'] for t in self.trade_history[-10:]])  # Last 10 trades

            # Calculate drawdown
            balance_curve = [account_balance]
            for trade in self.trade_history:
                balance_curve.append(balance_curve[-1] + trade['profit'])

            peak = balance_curve[0]
            max_dd = 0
            for balance in balance_curve:
                if balance > peak:
                    peak = balance
                dd = (peak - balance) / peak if peak > 0 else 0
                max_dd = max(max_dd, dd)

            # Sharpe ratio (simplified)
            returns = [t['profit'] / account_balance for t in self.trade_history]
            if len(returns) > 1:
                sharpe = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
            else:
                sharpe = 0

            # Sortino ratio (only downside deviation)
            negative_returns = [r for r in returns if r < 0]
            if negative_returns:
                sortino = np.mean(returns) / np.std(negative_returns) if np.std(negative_returns) > 0 else 0
            else:
                sortino = sharpe

            # Profit factor
            total_wins = sum([t['profit'] for t in wins])
            total_losses = abs(sum([t['profit'] for t in losses]))
            profit_factor = total_wins / total_losses if total_losses > 0 else 0

            # Expectancy
            expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

            # Kelly percentage
            kelly_pct = self.calculate_kelly_criterion(win_rate, avg_win, avg_loss)

            return RiskMetrics(
                total_exposure=total_exposure,
                max_drawdown=max_dd * 100,
                sharpe_ratio=sharpe,
                sortino_ratio=sortino,
                win_rate=win_rate * 100,
                avg_win=avg_win,
                avg_loss=avg_loss,
                profit_factor=profit_factor,
                expectancy=expectancy,
                kelly_percentage=kelly_pct * 100
            )

        except Exception as e:
            logger.error(f"Error calculating portfolio metrics: {e}")
            return RiskMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

    def check_signal(self, signal: Dict, account_balance: float = 0,
                    current_exposure: float = 0, open_positions: Dict = None) -> Dict:
        """
        Check if signal passes risk management rules
        Compatible with order_manager expectations
        Returns dict with 'allowed' and 'reason' keys
        """
        try:
            open_positions = open_positions or {}

            # Check if trading should be halted
            if account_balance > 0:
                should_halt, reason = self.should_halt_trading(account_balance)
                if should_halt:
                    return {'allowed': False, 'reason': f"Trading halted: {reason}"}

            # Check max concurrent positions
            max_positions = self.config.get('max_concurrent_trades', 3)
            if len(open_positions) >= max_positions:
                return {'allowed': False, 'reason': f"Maximum concurrent positions: {len(open_positions)}/{max_positions}"}

            # Check daily loss limit
            if self.daily_pnl < 0 and account_balance > 0:
                daily_loss_pct = (abs(self.daily_pnl) / account_balance) * 100
                if daily_loss_pct >= self.max_daily_loss_pct * 0.8:  # 80% of limit
                    return {'allowed': False, 'reason': f"Approaching daily loss limit: {daily_loss_pct:.2f}%"}

            # Check consecutive losses
            if self.recent_losses >= 3:
                return {'allowed': False, 'reason': f"Too many consecutive losses: {self.recent_losses}"}

            # Check exposure limits
            if account_balance > 0 and current_exposure > 0:
                exposure_pct = (current_exposure / account_balance) * 100
                if exposure_pct >= self.max_portfolio_exposure:
                    return {'allowed': False, 'reason': f"Portfolio exposure limit: {exposure_pct:.2f}%"}

            return {'allowed': True, 'reason': 'OK'}

        except Exception as e:
            logger.error(f"Error checking signal: {e}")
            return {'allowed': False, 'reason': f"Error: {str(e)}"}

    def calculate_lot_size(self, signal: Dict, account_balance: float = 0) -> float:
        """
        Calculate lot size for a signal
        Compatible with order_manager expectations
        """
        try:
            # Extract signal parameters
            symbol = signal.get('symbol', self.config.get('symbol', 'BTCUSD'))
            entry_price = signal.get('entry_price', 0)
            sl_price = signal.get('sl_price', 0)

            if entry_price <= 0 or sl_price <= 0:
                logger.warning("Invalid signal prices for lot calculation")
                return 0.01  # Minimum lot

            # Use account balance from signal or parameter
            if account_balance <= 0:
                account_balance = signal.get('account_balance', 1000)

            # Calculate position size using advanced method
            position_risk = self.calculate_position_size(
                symbol=symbol,
                entry_price=entry_price,
                stop_loss=sl_price,
                account_balance=account_balance,
                current_volatility=1.0
            )

            if position_risk and position_risk.position_size > 0:
                return position_risk.position_size

            # Fallback: basic calculation
            risk_amount = account_balance * (self.base_risk_pct / 100)
            sl_distance = abs(entry_price - sl_price)

            if sl_distance > 0:
                # Simple lot calculation
                lot_size = risk_amount / (sl_distance * 100)  # Approximate
                return max(0.01, min(lot_size, 10.0))  # Clamp between 0.01 and 10

            return 0.01  # Minimum fallback

        except Exception as e:
            logger.error(f"Error calculating lot size: {e}")
            return 0.01

    def should_halt_trading(self, current_balance: float) -> Tuple[bool, str]:
        """Determine if trading should be halted due to risk limits"""
        try:
            # Calculate current drawdown
            if self.peak_balance > 0:
                current_dd = ((self.peak_balance - current_balance) / self.peak_balance) * 100

                # Halt if drawdown exceeds 20%
                if current_dd > 20:
                    return True, f"Maximum drawdown exceeded: {current_dd:.2f}%"

            # Check daily loss
            if self.daily_pnl < 0 and current_balance > 0:
                daily_loss_pct = (abs(self.daily_pnl) / current_balance) * 100
                if daily_loss_pct >= self.max_daily_loss_pct:
                    return True, f"Daily loss limit: {daily_loss_pct:.2f}%"

            # Check consecutive losses
            if self.recent_losses >= 5:
                return True, f"Too many consecutive losses: {self.recent_losses}"

            return False, "OK"

        except Exception as e:
            logger.error(f"Error checking halt condition: {e}")
            return True, f"Error: {str(e)}"

    def get_risk_summary(self, account_balance: float) -> Dict:
        """Get comprehensive risk summary"""
        try:
            metrics = self.calculate_portfolio_metrics(account_balance)

            return {
                'account_balance': account_balance,
                'peak_balance': self.peak_balance,
                'daily_pnl': self.daily_pnl,
                'weekly_pnl': self.weekly_pnl,
                'monthly_pnl': self.monthly_pnl,
                'max_drawdown_pct': metrics.max_drawdown,
                'win_rate_pct': metrics.win_rate,
                'profit_factor': metrics.profit_factor,
                'sharpe_ratio': metrics.sharpe_ratio,
                'expectancy': metrics.expectancy,
                'kelly_pct': metrics.kelly_percentage,
                'risk_scaling': self.risk_scaling_factor,
                'consecutive_losses': self.recent_losses,
                'total_trades': len(self.trade_history)
            }

        except Exception as e:
            logger.error(f"Error getting risk summary: {e}")
            return {}
