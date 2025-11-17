"""
Advanced Position Management Module
Implements trailing stops, partial profit taking, break-even management, and dynamic SL/TP
Enhanced with Dynamic ATR-based trailing and MFE (Maximum Favorable Excursion) protection
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Position details with ATR and MFE tracking"""
    ticket: int
    symbol: str
    side: str  # 'BUY' or 'SELL'
    entry_price: float
    current_price: float
    volume: float
    stop_loss: float
    take_profit: float
    open_time: datetime
    profit: float
    profit_pct: float
    highest_price: float = 0.0  # For trailing stop
    lowest_price: float = 0.0   # For trailing stop
    break_even_activated: bool = False
    partial_profit_taken: List[float] = field(default_factory=list)
    max_profit_reached: float = 0.0
    max_loss_reached: float = 0.0

    # ATR and MFE tracking
    initial_risk_points: float = 0.0  # Entry - SL distance
    best_profit_points: float = 0.0   # MFE tracking
    best_profit_price: float = 0.0    # Price at best profit
    bars_since_new_best: int = 0      # Consolidation detection
    atr_at_entry: float = 0.0         # ATR when position opened
    current_atr: float = 0.0          # Current ATR value


@dataclass
class TrailingStopConfig:
    """Trailing stop configuration"""
    activation_pct: float  # Activate trailing after this % profit
    trailing_pct: float    # Trail by this % from peak
    step_pct: float       # Move in steps of this %


class AdvancedPositionManager:
    """
    Professional position management with trailing stops, partial profits, and break-even
    """

    def __init__(self, config: Dict):
        """Initialize advanced position manager"""
        self.config = config

        # NEW: Dynamic ATR system (can be disabled to use old system)
        self.use_dynamic_atr = config.get('use_dynamic_atr_trailing', False)
        self.atr_period = config.get('atr_period', 14)
        self.atr_timeframe = config.get('atr_timeframe', 'M5')

        # ATR multipliers by profit level (adapts to volatility)
        self.atr_multipliers = config.get('atr_trail_multipliers', {
            'initial': 2.0,       # Wide when profit < 1x risk
            'conservative': 1.5,  # Normal when profit 1-3x risk
            'aggressive': 1.2,    # Tight when profit > 3x risk
            'exit': 0.8          # Very tight when consolidating
        })

        # MFE (Maximum Favorable Excursion) profit lock levels
        self.mfe_locks = config.get('mfe_profit_locks', [
            {'trigger_risk_multiple': 1.5, 'lock_pct': 30},  # At 1.5x risk, lock 30% of best
            {'trigger_risk_multiple': 2.5, 'lock_pct': 40},  # At 2.5x risk, lock 40% of best
            {'trigger_risk_multiple': 4.0, 'lock_pct': 50}   # At 4x risk, lock 50% of best
        ])

        # Reversal detection (subtle - just tightens trail, doesn't close)
        self.reversal_detection = config.get('enable_reversal_detection', True)
        self.reversal_threshold_pct = config.get('reversal_threshold_pct', 25)  # 25% reversal from best

        # Consolidation detection (price stalling after good move)
        self.consolidation_bars = config.get('consolidation_bars_threshold', 20)

        # Original position management settings (still used as fallback)
        self.enable_trailing_stop = config.get('enable_trailing_stop', True)
        self.trailing_activation_pct = config.get('trailing_activation_pct', 1.0)
        self.trailing_distance_pct = config.get('trailing_distance_pct', 0.5)
        self.trailing_step_pct = config.get('trailing_step_pct', 0.25)

        self.enable_break_even = config.get('enable_break_even', True)
        self.break_even_activation_pct = config.get('break_even_activation_pct', 0.5)
        self.break_even_buffer_pct = config.get('break_even_buffer_pct', 0.1)

        self.enable_partial_profit = config.get('enable_partial_profit', True)
        self.partial_profit_levels = config.get('partial_profit_levels', [
            {'pct': 1.0, 'close_pct': 30},   # Close 30% at 1% profit
            {'pct': 2.0, 'close_pct': 30},   # Close 30% at 2% profit
            {'pct': 3.0, 'close_pct': 40}    # Close 40% at 3% profit
        ])

        self.max_position_hold_hours = config.get('max_position_hold_hours', 24)

        # Active positions tracking
        self.positions: Dict[int, Position] = {}

        if self.use_dynamic_atr:
            logger.info("Advanced Position Manager initialized with DYNAMIC ATR + MFE system")
        else:
            logger.info("Advanced Position Manager initialized with standard trailing")

    def add_position(self, ticket: int, symbol: str, side: str, entry_price: float,
                    volume: float, stop_loss: float, take_profit: float,
                    open_time: datetime, atr: float = 0.0) -> Position:
        """Add a new position to track"""
        try:
            # Calculate initial risk
            if side == 'BUY':
                initial_risk = entry_price - stop_loss
            else:
                initial_risk = stop_loss - entry_price

            position = Position(
                ticket=ticket,
                symbol=symbol,
                side=side,
                entry_price=entry_price,
                current_price=entry_price,
                volume=volume,
                stop_loss=stop_loss,
                take_profit=take_profit,
                open_time=open_time,
                profit=0.0,
                profit_pct=0.0,
                highest_price=entry_price if side == 'BUY' else 0,
                lowest_price=entry_price if side == 'SELL' else float('inf'),
                initial_risk_points=initial_risk,
                best_profit_points=0.0,
                best_profit_price=entry_price,
                atr_at_entry=atr if atr > 0 else initial_risk * 0.5,  # Estimate if not provided
                current_atr=atr if atr > 0 else initial_risk * 0.5
            )

            self.positions[ticket] = position
            logger.info(f"Added position {ticket} for {symbol} {side} @ {entry_price} "
                       f"(Risk: {initial_risk:.2f}, ATR: {position.atr_at_entry:.2f})")

            return position

        except Exception as e:
            logger.error(f"Error adding position: {e}")
            return None

    def update_position(self, ticket: int, current_price: float,
                       mt5_client) -> Optional[Dict]:
        """
        Update position and manage trailing stop, break-even, partial profits
        Returns action to take: {'action': 'modify_sl', 'new_sl': xxx} or None
        """
        try:
            if ticket not in self.positions:
                return None

            position = self.positions[ticket]
            position.current_price = current_price

            # Calculate profit
            # Safety check: entry_price should never be 0, but validate anyway
            if position.entry_price <= 0:
                logger.error(f"Invalid entry_price {position.entry_price} for position {ticket}")
                return None

            if position.side == 'BUY':
                profit_pips = current_price - position.entry_price
                position.profit_pct = (profit_pips / position.entry_price) * 100

                # Update highest price for trailing
                if current_price > position.highest_price:
                    position.highest_price = current_price

            else:  # SELL
                profit_pips = position.entry_price - current_price
                position.profit_pct = (profit_pips / position.entry_price) * 100

                # Update lowest price for trailing
                if current_price < position.lowest_price:
                    position.lowest_price = current_price

            # Update max profit/loss reached
            if position.profit_pct > position.max_profit_reached:
                position.max_profit_reached = position.profit_pct

            if position.profit_pct < 0 and abs(position.profit_pct) > abs(position.max_loss_reached):
                position.max_loss_reached = position.profit_pct

            # Check for partial profit taking
            if self.enable_partial_profit:
                partial_action = self._check_partial_profit(position, mt5_client)
                if partial_action:
                    return partial_action

            # Check for break-even
            if self.enable_break_even and not position.break_even_activated:
                be_action = self._check_break_even(position)
                if be_action:
                    position.break_even_activated = True
                    return be_action

            # Check for trailing stop (Dynamic ATR or Standard)
            if self.enable_trailing_stop:
                if self.use_dynamic_atr:
                    # NEW: Dynamic ATR + MFE system
                    trailing_action = self._check_dynamic_atr_trailing(position, mt5_client)
                else:
                    # OLD: Standard fixed percentage trailing
                    trailing_action = self._check_trailing_stop(position)

                if trailing_action:
                    return trailing_action

            # Check time-based exit
            time_action = self._check_time_exit(position)
            if time_action:
                return time_action

            return None

        except Exception as e:
            logger.error(f"Error updating position {ticket}: {e}")
            return None

    def _check_break_even(self, position: Position) -> Optional[Dict]:
        """Check if break-even should be activated"""
        try:
            if position.profit_pct >= self.break_even_activation_pct:
                # Move stop loss to break-even + buffer
                if position.side == 'BUY':
                    new_sl = position.entry_price * (1 + self.break_even_buffer_pct / 100)

                    # Only move if new SL is better than current
                    if new_sl > position.stop_loss:
                        logger.info(f"Activating break-even for position {position.ticket}: "
                                  f"moving SL from {position.stop_loss} to {new_sl}")
                        return {
                            'action': 'modify_sl',
                            'ticket': position.ticket,
                            'new_sl': new_sl,
                            'reason': 'break_even'
                        }

                else:  # SELL
                    new_sl = position.entry_price * (1 - self.break_even_buffer_pct / 100)

                    if new_sl < position.stop_loss:
                        logger.info(f"Activating break-even for position {position.ticket}: "
                                  f"moving SL from {position.stop_loss} to {new_sl}")
                        return {
                            'action': 'modify_sl',
                            'ticket': position.ticket,
                            'new_sl': new_sl,
                            'reason': 'break_even'
                        }

            return None

        except Exception as e:
            logger.error(f"Error checking break-even: {e}")
            return None

    def _check_trailing_stop(self, position: Position) -> Optional[Dict]:
        """Check if trailing stop should be updated"""
        try:
            # Only activate trailing after reaching activation threshold
            if position.profit_pct < self.trailing_activation_pct:
                return None

            if position.side == 'BUY':
                # Calculate new trailing stop
                trailing_distance = position.highest_price * (self.trailing_distance_pct / 100)
                new_sl = position.highest_price - trailing_distance

                # Only move if new SL is significantly better (avoid too frequent updates)
                sl_improvement = new_sl - position.stop_loss
                min_improvement = position.entry_price * (self.trailing_step_pct / 100)

                if new_sl > position.stop_loss and sl_improvement >= min_improvement:
                    logger.info(f"Trailing stop for position {position.ticket}: "
                              f"moving SL from {position.stop_loss:.5f} to {new_sl:.5f} "
                              f"(highest: {position.highest_price:.5f})")
                    return {
                        'action': 'modify_sl',
                        'ticket': position.ticket,
                        'new_sl': new_sl,
                        'reason': 'trailing_stop'
                    }

            else:  # SELL
                trailing_distance = position.lowest_price * (self.trailing_distance_pct / 100)
                new_sl = position.lowest_price + trailing_distance

                sl_improvement = position.stop_loss - new_sl
                min_improvement = position.entry_price * (self.trailing_step_pct / 100)

                if new_sl < position.stop_loss and sl_improvement >= min_improvement:
                    logger.info(f"Trailing stop for position {position.ticket}: "
                              f"moving SL from {position.stop_loss:.5f} to {new_sl:.5f} "
                              f"(lowest: {position.lowest_price:.5f})")
                    return {
                        'action': 'modify_sl',
                        'ticket': position.ticket,
                        'new_sl': new_sl,
                        'reason': 'trailing_stop'
                    }

            return None

        except Exception as e:
            logger.error(f"Error checking trailing stop: {e}")
            return None

    def _check_partial_profit(self, position: Position, mt5_client) -> Optional[Dict]:
        """Check if partial profit should be taken"""
        try:
            for level in self.partial_profit_levels:
                profit_threshold = level['pct']
                close_pct = level['close_pct']

                # Check if we've reached this level and haven't taken profit yet
                if (position.profit_pct >= profit_threshold and
                    profit_threshold not in position.partial_profit_taken):

                    # Calculate volume to close
                    close_volume = position.volume * (close_pct / 100)

                    logger.info(f"Taking partial profit for position {position.ticket}: "
                              f"closing {close_pct}% ({close_volume:.2f} lots) at {profit_threshold}% profit")

                    position.partial_profit_taken.append(profit_threshold)

                    return {
                        'action': 'partial_close',
                        'ticket': position.ticket,
                        'volume': close_volume,
                        'reason': f'partial_profit_{profit_threshold}pct'
                    }

            return None

        except Exception as e:
            logger.error(f"Error checking partial profit: {e}")
            return None

    def _check_dynamic_atr_trailing(self, position: Position, mt5_client) -> Optional[Dict]:
        """
        BULLETPROOF Dynamic ATR + MFE trailing system for BTC
        Adapts to volatility and locks profit on big moves
        """
        try:
            # Get current ATR
            try:
                df = mt5_client.get_bars(self.atr_timeframe, self.atr_period + 20)
                if df is not None and len(df) >= self.atr_period:
                    from indicators import Indicators
                    atr_series = Indicators.atr(df, self.atr_period)
                    position.current_atr = atr_series.iloc[-1] if len(atr_series) > 0 else position.atr_at_entry
                else:
                    position.current_atr = position.atr_at_entry  # Fallback
            except Exception as e:
                logger.warning(f"Could not get ATR, using entry ATR: {e}")
                position.current_atr = position.atr_at_entry

            # Calculate profit in points
            if position.side == 'BUY':
                profit_points = position.current_price - position.entry_price
                best_price = position.highest_price
            else:  # SELL
                profit_points = position.entry_price - position.current_price
                best_price = position.lowest_price

            # Update MFE (Maximum Favorable Excursion)
            if profit_points > position.best_profit_points:
                position.best_profit_points = profit_points
                position.best_profit_price = position.current_price
                position.bars_since_new_best = 0
            else:
                position.bars_since_new_best += 1

            # Calculate risk multiple (how many times initial risk we've made)
            risk_multiple = profit_points / position.initial_risk_points if position.initial_risk_points > 0 else 0

            # ==== PHASE 1: Not profitable yet - no trailing ====
            if risk_multiple < 0.3:  # Less than 30% of risk
                return None

            # ==== PHASE 2: Small profit - conservative trailing ====
            if risk_multiple < 1.0:
                atr_multiplier = self.atr_multipliers.get('initial', 2.0)
                trail_distance = position.current_atr * atr_multiplier

            # ==== PHASE 3: Good profit (1-3x risk) - standard trailing ====
            elif risk_multiple < 3.0:
                atr_multiplier = self.atr_multipliers.get('conservative', 1.5)
                trail_distance = position.current_atr * atr_multiplier

            # ==== PHASE 4: Big profit (3x+ risk) - MFE PROTECTION ACTIVATED ====
            else:
                # This is the bulletproof part for your 743-point example!
                atr_multiplier = self.atr_multipliers.get('aggressive', 1.2)
                atr_trail = position.current_atr * atr_multiplier

                # Calculate MFE lock (lock percentage of best profit)
                mfe_lock_pct = 0.0
                for lock_level in self.mfe_locks:
                    if risk_multiple >= lock_level['trigger_risk_multiple']:
                        mfe_lock_pct = lock_level['lock_pct']

                # MFE lock: minimum profit to protect
                mfe_lock_points = position.best_profit_points * (mfe_lock_pct / 100)

                # Use TIGHTER of ATR trail or MFE lock (more aggressive protection)
                trail_distance = min(atr_trail, position.best_profit_points - mfe_lock_points)

                logger.debug(f"Position {position.ticket} BIG MOVE: {risk_multiple:.1f}x risk, "
                           f"Best: {position.best_profit_points:.1f} pts, "
                           f"MFE lock: {mfe_lock_pct}% = {mfe_lock_points:.1f} pts, "
                           f"ATR trail: {atr_trail:.1f} pts, Using: {trail_distance:.1f} pts")

            # ==== REVERSAL DETECTION (Subtle tightening) ====
            if self.reversal_detection and risk_multiple >= 1.5:
                # Check if price has reversed significantly from best
                reversal_pct = ((position.best_profit_points - profit_points) / position.best_profit_points * 100) if position.best_profit_points > 0 else 0

                if reversal_pct >= self.reversal_threshold_pct:
                    # Price reversed 25%+ from best - tighten trail
                    logger.info(f"Position {position.ticket} REVERSAL DETECTED: {reversal_pct:.1f}% from best, tightening trail")
                    trail_distance = position.current_atr * self.atr_multipliers.get('aggressive', 1.2)

            # ==== CONSOLIDATION DETECTION ====
            if position.bars_since_new_best >= self.consolidation_bars:
                # Price stalling - exit mode
                logger.info(f"Position {position.ticket} CONSOLIDATING: {position.bars_since_new_best} bars without new best, very tight trail")
                trail_distance = position.current_atr * self.atr_multipliers.get('exit', 0.8)

            # Calculate new stop loss
            if position.side == 'BUY':
                new_sl = best_price - trail_distance

                # Only move if significantly better (avoid noise)
                min_improvement = position.entry_price * 0.001  # 0.1% minimum move
                if new_sl > position.stop_loss and (new_sl - position.stop_loss) >= min_improvement:
                    logger.info(f"Dynamic ATR trailing {position.ticket}: SL {position.stop_loss:.2f} → {new_sl:.2f} "
                              f"(Risk: {risk_multiple:.1f}x, ATR: {position.current_atr:.2f}, Trail: {trail_distance:.2f})")
                    return {
                        'action': 'modify_sl',
                        'ticket': position.ticket,
                        'new_sl': new_sl,
                        'reason': f'dynamic_atr_trail_{risk_multiple:.1f}x'
                    }

            else:  # SELL
                new_sl = best_price + trail_distance

                min_improvement = position.entry_price * 0.001
                if new_sl < position.stop_loss and (position.stop_loss - new_sl) >= min_improvement:
                    logger.info(f"Dynamic ATR trailing {position.ticket}: SL {position.stop_loss:.2f} → {new_sl:.2f} "
                              f"(Risk: {risk_multiple:.1f}x, ATR: {position.current_atr:.2f}, Trail: {trail_distance:.2f})")
                    return {
                        'action': 'modify_sl',
                        'ticket': position.ticket,
                        'new_sl': new_sl,
                        'reason': f'dynamic_atr_trail_{risk_multiple:.1f}x'
                    }

            return None

        except Exception as e:
            logger.error(f"Error in dynamic ATR trailing: {e}")
            # Fallback to standard trailing
            return self._check_trailing_stop(position)

    def _check_time_exit(self, position: Position) -> Optional[Dict]:
        """Check if position should be closed due to time limit"""
        try:
            hours_held = (datetime.utcnow() - position.open_time).total_seconds() / 3600

            if hours_held >= self.max_position_hold_hours:
                logger.info(f"Time-based exit for position {position.ticket}: "
                          f"held for {hours_held:.1f} hours")
                return {
                    'action': 'close_position',
                    'ticket': position.ticket,
                    'reason': 'time_exit'
                }

            return None

        except Exception as e:
            logger.error(f"Error checking time exit: {e}")
            return None

    def remove_position(self, ticket: int) -> Optional[Position]:
        """Remove position from tracking"""
        try:
            if ticket in self.positions:
                position = self.positions.pop(ticket)
                logger.info(f"Removed position {ticket} from tracking")
                return position

            return None

        except Exception as e:
            logger.error(f"Error removing position {ticket}: {e}")
            return None

    def get_position_summary(self, ticket: int) -> Optional[Dict]:
        """Get summary of a position"""
        try:
            if ticket not in self.positions:
                return None

            position = self.positions[ticket]

            return {
                'ticket': position.ticket,
                'symbol': position.symbol,
                'side': position.side,
                'entry_price': position.entry_price,
                'current_price': position.current_price,
                'volume': position.volume,
                'stop_loss': position.stop_loss,
                'take_profit': position.take_profit,
                'profit_pct': position.profit_pct,
                'max_profit_pct': position.max_profit_reached,
                'max_loss_pct': position.max_loss_reached,
                'break_even_active': position.break_even_activated,
                'partial_profits_taken': len(position.partial_profit_taken),
                'hours_held': (datetime.utcnow() - position.open_time).total_seconds() / 3600
            }

        except Exception as e:
            logger.error(f"Error getting position summary: {e}")
            return None

    def get_all_positions_summary(self) -> List[Dict]:
        """Get summary of all positions"""
        try:
            summaries = []

            for ticket in self.positions:
                summary = self.get_position_summary(ticket)
                if summary:
                    summaries.append(summary)

            return summaries

        except Exception as e:
            logger.error(f"Error getting all positions summary: {e}")
            return []

    def execute_position_action(self, action: Dict, mt5_client) -> bool:
        """Execute position management action via MT5"""
        try:
            action_type = action.get('action')

            if action_type == 'modify_sl':
                ticket = action['ticket']
                new_sl = action['new_sl']

                # Get current position details
                if ticket not in self.positions:
                    return False

                position = self.positions[ticket]

                # Modify stop loss via MT5
                success = mt5_client.modify_position(
                    ticket=ticket,
                    stop_loss=new_sl,
                    take_profit=position.take_profit
                )

                if success:
                    position.stop_loss = new_sl
                    logger.info(f"Modified SL for {ticket} to {new_sl}")
                    return True

            elif action_type == 'partial_close':
                ticket = action['ticket']
                volume = action['volume']

                # Close partial position via MT5
                success = mt5_client.close_position_partial(
                    ticket=ticket,
                    volume=volume
                )

                if success:
                    position = self.positions[ticket]
                    position.volume -= volume
                    logger.info(f"Closed partial {volume} lots for {ticket}")
                    return True

            elif action_type == 'close_position':
                ticket = action['ticket']

                # Close entire position via MT5
                success = mt5_client.close_position(ticket=ticket)

                if success:
                    self.remove_position(ticket)
                    logger.info(f"Closed position {ticket}")
                    return True

            return False

        except Exception as e:
            logger.error(f"Error executing position action: {e}")
            return False

    def get_average_hold_time(self) -> float:
        """Get average position hold time in hours"""
        try:
            if not self.positions:
                return 0.0

            total_hours = 0
            for position in self.positions.values():
                hours = (datetime.utcnow() - position.open_time).total_seconds() / 3600
                total_hours += hours

            return total_hours / len(self.positions)

        except Exception as e:
            logger.error(f"Error calculating average hold time: {e}")
            return 0.0
