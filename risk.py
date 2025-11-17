"""
Risk Management Module
Handles position sizing, exposure limits, and risk calculations
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Manages trading risk including position sizing and exposure limits
    """
    
    def __init__(self, config: Dict, mt5_client, persistence):
        self.config = config
        self.mt5_client = mt5_client
        self.persistence = persistence
        self.daily_stats = self._initialize_daily_stats()
        
    def _initialize_daily_stats(self) -> Dict:
        """
        Initialize or load daily statistics
        """
        return {
            'date': datetime.now(timezone.utc).date(),
            'trades_taken': 0,
            'trades_won': 0,
            'trades_lost': 0,
            'profit': 0.0,
            'loss': 0.0,
            'max_drawdown': 0.0,
            'starting_balance': None,
        }
    
    def calculate_lot_size(self, signal: Dict) -> float:
        """
        Calculate appropriate lot size based on risk parameters
        """
        try:
            # Check if using fixed lot size
            if self.config.get('use_fixed_lot', False):
                fixed_lot = self.config.get('fixed_lot', 0.01)
                return self._validate_lot_size(fixed_lot)
            
            # Get account info
            account = self.mt5_client.get_account_info()
            if not account:
                logger.error("Cannot get account info for lot calculation")
                return 0.0
            
            balance = account['balance']
            
            # Calculate risk amount
            risk_pct = self.config.get('risk_pct_per_trade', 0.5)
            risk_amount = balance * (risk_pct / 100)
            
            # Calculate stop loss distance in points
            sl_distance = abs(signal['entry_price'] - signal['sl_price'])
            
            # Get symbol info
            symbol_info = self.mt5_client.symbol_info
            if not symbol_info:
                logger.error("Symbol info not available")
                return 0.0

            point = symbol_info['point']
            contract_size = symbol_info['contract_size']

            # Safety check: point should never be 0, but validate
            if point <= 0:
                logger.error(f"Invalid point value: {point}")
                return 0.0

            # Calculate sl distance in points
            sl_points = sl_distance / point
            
            # Calculate lot size
            # Risk = Lots * Contract_Size * SL_Points * Point_Value
            # For gold, typically: contract_size = 100, point = 0.01, point_value varies

            # Get tick value for proper calculation
            tick_value = symbol_info.get('tick_value', 1.0)
            tick_size = symbol_info.get('tick_size', point)

            if tick_size > 0 and tick_value > 0:
                # Proper lot calculation
                point_value = tick_value * (point / tick_size)
                if point_value > 0 and sl_points > 0 and contract_size > 0:
                    lots = risk_amount / (sl_points * point_value * contract_size)
                else:
                    # Fallback if calculations are invalid
                    lots = risk_amount / (sl_distance * contract_size) if sl_distance > 0 and contract_size > 0 else 0.01
            else:
                # Fallback calculation
                lots = risk_amount / (sl_distance * contract_size) if sl_distance > 0 and contract_size > 0 else 0.01

            # CRITICAL FIX: DO NOT multiply by leverage!
            # Leverage is already factored into margin requirements by the broker.
            # The lot size should be based ONLY on risk amount and SL distance.
            # Previous buggy code removed: lots = lots * (leverage / 100)
            # This was causing position sizes to be multiplied by (leverage/100), which:
            # - For 1:500 leverage: multiplied by 5 (500/100) = 5x oversized positions!
            # - For 1:100 leverage: multiplied by 1 (100/100) = correct by accident
            # This bug would cause catastrophic losses on high-leverage accounts!
            
            # Validate and round lot size
            validated_lots = self._validate_lot_size(lots)
            
            logger.info(f"Calculated lot size: {validated_lots:.2f} "
                       f"(Risk: ${risk_amount:.2f}, SL: {sl_points:.1f} points)")
            
            return validated_lots
            
        except Exception as e:
            logger.error(f"Error calculating lot size: {e}")
            return 0.0
    
    def _validate_lot_size(self, lots: float) -> float:
        """
        Validate and round lot size according to broker requirements
        """
        try:
            symbol_info = self.mt5_client.symbol_info
            if not symbol_info:
                return 0.01  # Default minimum
            
            min_lot = symbol_info['min_lot']
            max_lot = symbol_info['max_lot']
            lot_step = symbol_info['lot_step']
            
            # Clamp to min/max
            lots = max(min_lot, min(lots, max_lot))
            
            # Round to lot step
            if lot_step > 0:
                lots = round(lots / lot_step) * lot_step
            
            # Ensure minimum
            if lots < min_lot:
                lots = min_lot
            
            return round(lots, 2)  # Most brokers use 2 decimal places for lots
            
        except Exception as e:
            logger.error(f"Error validating lot size: {e}")
            return 0.01
    
    def check_signal(self, signal: Dict) -> Dict:
        """
        Check if signal passes risk management rules
        """
        try:
            result = {
                'allowed': True,
                'reason': '',
                'checks': {}
            }
            
            # Get account info
            account = self.mt5_client.get_account_info()
            if not account:
                return {'allowed': False, 'reason': 'Cannot get account info'}
            
            # Check daily loss limit
            daily_loss_check = self._check_daily_loss_limit(account)
            result['checks']['daily_loss'] = daily_loss_check
            if not daily_loss_check['passed']:
                result['allowed'] = False
                result['reason'] = daily_loss_check['message']
                return result
            
            # Check maximum exposure
            exposure_check = self._check_max_exposure(account)
            result['checks']['exposure'] = exposure_check
            if not exposure_check['passed']:
                result['allowed'] = False
                result['reason'] = exposure_check['message']
                return result
            
            # Check margin requirements
            margin_check = self._check_margin_requirements(account, signal)
            result['checks']['margin'] = margin_check
            if not margin_check['passed']:
                result['allowed'] = False
                result['reason'] = margin_check['message']
                return result
            
            # Check consecutive losses
            consecutive_check = self._check_consecutive_losses()
            result['checks']['consecutive_losses'] = consecutive_check
            if not consecutive_check['passed']:
                result['allowed'] = False
                result['reason'] = consecutive_check['message']
                return result
            
            return result
            
        except Exception as e:
            logger.error(f"Error checking signal risk: {e}")
            return {'allowed': False, 'reason': f'Risk check error: {e}'}
    
    def _check_daily_loss_limit(self, account: Dict) -> Dict:
        """
        Check if daily loss limit has been reached
        """
        try:
            # Update daily stats if new day
            current_date = datetime.now(timezone.utc).date()
            if current_date != self.daily_stats['date']:
                self.daily_stats = self._initialize_daily_stats()
                self.daily_stats['starting_balance'] = account['balance']
            
            # Set starting balance if not set
            if self.daily_stats['starting_balance'] is None:
                self.daily_stats['starting_balance'] = account['balance']
            
            # Calculate daily P&L
            daily_pnl = account['balance'] - self.daily_stats['starting_balance']
            daily_pnl_pct = (daily_pnl / self.daily_stats['starting_balance']) * 100 if self.daily_stats['starting_balance'] > 0 else 0
            
            # Check against limit
            max_daily_loss_pct = self.config.get('max_daily_loss_pct', 2.0)
            
            if daily_pnl_pct <= -max_daily_loss_pct:
                return {
                    'passed': False,
                    'message': f'Daily loss limit reached: {daily_pnl_pct:.2f}%',
                    'daily_pnl': daily_pnl,
                    'daily_pnl_pct': daily_pnl_pct,
                }
            
            return {
                'passed': True,
                'message': 'Within daily loss limit',
                'daily_pnl': daily_pnl,
                'daily_pnl_pct': daily_pnl_pct,
            }
            
        except Exception as e:
            logger.error(f"Error checking daily loss: {e}")
            return {'passed': True, 'message': 'Could not check daily loss'}
    
    def _check_max_exposure(self, account: Dict) -> Dict:
        """
        Check if maximum exposure limit would be exceeded
        """
        try:
            # Get current positions
            positions = self.mt5_client.get_positions(symbol=self.config['symbol'])
            
            # Calculate current exposure
            total_risk = 0.0
            for pos in positions:
                if pos.get('magic') == self.config.get('magic', 0):
                    # Calculate risk for each position
                    volume = pos['volume']
                    entry = pos['price']
                    sl = pos['sl']
                    
                    if sl > 0:
                        sl_distance = abs(entry - sl)
                        symbol_info = self.mt5_client.symbol_info
                        if symbol_info:
                            contract_size = symbol_info['contract_size']
                            position_risk = volume * sl_distance * contract_size
                            total_risk += position_risk
            
            # Calculate exposure percentage
            exposure_pct = (total_risk / account['balance']) * 100 if account['balance'] > 0 else 0
            
            # Check against limit
            max_exposure_pct = self.config.get('max_exposure_pct', 2.0)
            
            # Add new trade risk
            new_risk_pct = self.config.get('risk_pct_per_trade', 0.5)
            total_exposure = exposure_pct + new_risk_pct
            
            if total_exposure > max_exposure_pct:
                return {
                    'passed': False,
                    'message': f'Max exposure would be exceeded: {total_exposure:.2f}%',
                    'current_exposure': exposure_pct,
                    'new_exposure': total_exposure,
                }
            
            return {
                'passed': True,
                'message': 'Within exposure limits',
                'current_exposure': exposure_pct,
                'new_exposure': total_exposure,
            }
            
        except Exception as e:
            logger.error(f"Error checking exposure: {e}")
            return {'passed': True, 'message': 'Could not check exposure'}
    
    def _check_margin_requirements(self, account: Dict, signal: Dict) -> Dict:
        """
        Check if sufficient margin is available
        """
        try:
            free_margin = account.get('free_margin', 0)
            
            # Estimate required margin for new position
            symbol_info = self.mt5_client.symbol_info
            if not symbol_info:
                return {'passed': True, 'message': 'Cannot check margin'}
            
            # Simple margin calculation (varies by broker)
            estimated_lots = 0.01  # Use minimum for estimation
            contract_size = symbol_info['contract_size']
            leverage = account.get('leverage', 1)
            
            required_margin = (signal['entry_price'] * estimated_lots * contract_size) / leverage
            
            # Add safety buffer
            required_margin *= 1.2  # 20% buffer
            
            if free_margin < required_margin:
                return {
                    'passed': False,
                    'message': f'Insufficient margin: ${free_margin:.2f} < ${required_margin:.2f}',
                    'free_margin': free_margin,
                    'required_margin': required_margin,
                }
            
            margin_usage_pct = (required_margin / free_margin) * 100 if free_margin > 0 else 100
            
            return {
                'passed': True,
                'message': 'Sufficient margin available',
                'free_margin': free_margin,
                'required_margin': required_margin,
                'margin_usage_pct': margin_usage_pct,
            }
            
        except Exception as e:
            logger.error(f"Error checking margin: {e}")
            return {'passed': True, 'message': 'Could not check margin'}
    
    def _check_consecutive_losses(self) -> Dict:
        """
        Check for consecutive losses and adjust risk if needed
        """
        try:
            # Get recent trade history from persistence
            recent_trades = self.persistence.get_recent_trades(limit=10)
            
            if not recent_trades:
                return {'passed': True, 'message': 'No trade history'}
            
            # Count consecutive losses
            consecutive_losses = 0
            for trade in recent_trades:
                if trade.get('profit', 0) < 0:
                    consecutive_losses += 1
                else:
                    break
            
            # Define threshold
            max_consecutive = 3
            
            if consecutive_losses >= max_consecutive:
                return {
                    'passed': False,
                    'message': f'Too many consecutive losses: {consecutive_losses}',
                    'consecutive_losses': consecutive_losses,
                }
            
            return {
                'passed': True,
                'message': 'Consecutive loss check passed',
                'consecutive_losses': consecutive_losses,
            }
            
        except Exception as e:
            logger.error(f"Error checking consecutive losses: {e}")
            return {'passed': True, 'message': 'Could not check consecutive losses'}
    
    def update_trade_result(self, trade: Dict):
        """
        Update risk manager with trade result
        """
        try:
            # Update daily stats
            self.daily_stats['trades_taken'] += 1
            
            if trade.get('profit', 0) > 0:
                self.daily_stats['trades_won'] += 1
                self.daily_stats['profit'] += trade['profit']
            else:
                self.daily_stats['trades_lost'] += 1
                self.daily_stats['loss'] += abs(trade['profit'])
            
            # Calculate win rate
            if self.daily_stats['trades_taken'] > 0:
                win_rate = (self.daily_stats['trades_won'] / self.daily_stats['trades_taken']) * 100
                logger.info(f"Daily stats - Trades: {self.daily_stats['trades_taken']}, "
                           f"Win rate: {win_rate:.1f}%, "
                           f"P&L: ${self.daily_stats['profit'] - self.daily_stats['loss']:.2f}")
            
        except Exception as e:
            logger.error(f"Error updating trade result: {e}")
    
    def get_risk_metrics(self) -> Dict:
        """
        Get current risk metrics
        """
        try:
            account = self.mt5_client.get_account_info()
            if not account:
                return {}
            
            positions = self.mt5_client.get_positions(symbol=self.config['symbol'])
            my_positions = [p for p in positions if p.get('magic') == self.config.get('magic', 0)]
            
            # Calculate metrics
            total_exposure = sum(p['volume'] for p in my_positions)
            open_profit = sum(p.get('profit', 0) for p in my_positions)
            
            # Daily metrics
            daily_pnl = 0
            if self.daily_stats['starting_balance']:
                daily_pnl = account['balance'] - self.daily_stats['starting_balance']
            
            win_rate = 0
            if self.daily_stats['trades_taken'] > 0:
                win_rate = (self.daily_stats['trades_won'] / self.daily_stats['trades_taken']) * 100
            
            return {
                'account_balance': account['balance'],
                'account_equity': account['equity'],
                'free_margin': account['free_margin'],
                'margin_level': account.get('margin_level', 0),
                'open_positions': len(my_positions),
                'total_exposure': total_exposure,
                'open_profit': open_profit,
                'daily_trades': self.daily_stats['trades_taken'],
                'daily_pnl': daily_pnl,
                'daily_win_rate': win_rate,
                'max_daily_loss_pct': self.config.get('max_daily_loss_pct', 2.0),
                'max_exposure_pct': self.config.get('max_exposure_pct', 2.0),
                'risk_per_trade_pct': self.config.get('risk_pct_per_trade', 0.5),
            }
            
        except Exception as e:
            logger.error(f"Error getting risk metrics: {e}")
            return {}
