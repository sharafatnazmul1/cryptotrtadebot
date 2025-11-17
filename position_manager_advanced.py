"""
Advanced Position Management Module
Implements trailing stops, partial profit taking, break-even management, and dynamic SL/TP
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Position details"""
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
    partial_profit_taken: List[float] = None
    max_profit_reached: float = 0.0
    max_loss_reached: float = 0.0

    def __post_init__(self):
        if self.partial_profit_taken is None:
            self.partial_profit_taken = []


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

        # Position management settings
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

        logger.info("Advanced Position Manager initialized")

    def add_position(self, ticket: int, symbol: str, side: str, entry_price: float,
                    volume: float, stop_loss: float, take_profit: float,
                    open_time: datetime) -> Position:
        """Add a new position to track"""
        try:
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
                lowest_price=entry_price if side == 'SELL' else float('inf')
            )

            self.positions[ticket] = position
            logger.info(f"Added position {ticket} for {symbol} {side} @ {entry_price}")

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

            # Check for trailing stop
            if self.enable_trailing_stop:
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
