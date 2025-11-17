"""
Backtest Broker Simulator
Simulates realistic order execution with fills, slippage, commission, and spread
"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass
import MetaTrader5 as mt5

logger = logging.getLogger(__name__)


@dataclass
class SimulatedPosition:
    """Simulated open position"""
    ticket: int
    symbol: str
    type: str  # 'BUY' or 'SELL'
    volume: float
    price_open: float
    sl: float
    tp: float
    magic: int
    comment: str
    time_open: datetime
    commission: float = 0.0
    swap: float = 0.0
    profit: float = 0.0


@dataclass
class SimulatedOrder:
    """Simulated pending order"""
    ticket: int
    symbol: str
    type: str  # 'BUY_LIMIT', 'SELL_LIMIT', etc.
    volume: float
    price: float
    sl: float
    tp: float
    magic: int
    comment: str
    time_setup: datetime
    expiration: datetime


class BacktestBroker:
    """
    Simulates a real broker with realistic order execution
    """

    def __init__(self, config: Dict, initial_balance: float, symbol_info: Dict):
        """
        Initialize backtest broker

        Args:
            config: Trading config
            initial_balance: Starting account balance
            symbol_info: Symbol specifications
        """
        self.config = config
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.equity = initial_balance
        self.symbol_info = symbol_info

        # Trading state
        self.positions: Dict[int, SimulatedPosition] = {}
        self.orders: Dict[int, SimulatedOrder] = {}
        self.closed_trades: List[Dict] = []

        # Counters
        self.next_ticket = 1000
        self.trade_count = 0

        # Slippage and commission settings
        self.slippage_pips = config.get('backtest_slippage_pips', 2)
        self.commission_per_lot = config.get('backtest_commission_per_lot', 0.0)
        self.spread_multiplier = config.get('backtest_spread_multiplier', 1.0)

        logger.info(f"Backtest broker initialized: Balance=${initial_balance:.2f}, "
                   f"Slippage={self.slippage_pips} pips, Commission=${self.commission_per_lot}/lot")

    def get_account_info(self) -> Dict:
        """Get simulated account information"""
        # Calculate margin used
        margin_used = 0.0
        for pos in self.positions.values():
            leverage = self.config.get('leverage', 100)
            margin_used += (pos.price_open * pos.volume * self.symbol_info['contract_size']) / leverage

        free_margin = self.equity - margin_used
        margin_level = (self.equity / margin_used * 100) if margin_used > 0 else 0

        return {
            'balance': self.balance,
            'equity': self.equity,
            'margin': margin_used,
            'free_margin': free_margin,
            'margin_level': margin_level,
            'profit': sum(pos.profit for pos in self.positions.values()),
            'currency': 'USD',
            'leverage': self.config.get('leverage', 100),
            'limit_orders': len(self.orders),
        }

    def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get open positions"""
        positions = []

        for pos in self.positions.values():
            if symbol and pos.symbol != symbol:
                continue

            positions.append({
                'ticket': pos.ticket,
                'symbol': pos.symbol,
                'type': pos.type,
                'volume': pos.volume,
                'price': pos.price_open,
                'sl': pos.sl,
                'tp': pos.tp,
                'profit': pos.profit,
                'swap': pos.swap,
                'commission': pos.commission,
                'magic': pos.magic,
                'comment': pos.comment,
                'time': pos.time_open,
            })

        return positions

    def get_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get pending orders"""
        orders = []

        for order in self.orders.values():
            if symbol and order.symbol != symbol:
                continue

            orders.append({
                'ticket': order.ticket,
                'symbol': order.symbol,
                'type': order.type,
                'volume_current': order.volume,
                'price': order.price,
                'sl': order.sl,
                'tp': order.tp,
                'magic': order.magic,
                'comment': order.comment,
                'time_setup': order.time_setup,
                'time_expiration': order.expiration,
            })

        return orders

    def place_order(self, order_request: Dict, current_price: Dict,
                   current_time: datetime) -> Tuple[bool, Dict]:
        """
        Place an order (market or pending)

        Args:
            order_request: Order request dict
            current_price: Current market price {'bid': x, 'ask': y}
            current_time: Current simulation time

        Returns:
            (success, result_dict)
        """
        try:
            action = order_request['action']
            symbol = order_request['symbol']
            volume = order_request['volume']
            order_type = order_request['type']
            price = order_request.get('price', 0)
            sl = order_request.get('sl', 0)
            tp = order_request.get('tp', 0)
            magic = order_request.get('magic', 0)
            comment = order_request.get('comment', '')

            ticket = self._get_next_ticket()

            # Market order (instant execution)
            if action == mt5.TRADE_ACTION_DEAL:
                # Apply slippage
                if order_type == mt5.ORDER_TYPE_BUY:
                    execution_price = current_price['ask'] + self._get_slippage()
                else:  # SELL
                    execution_price = current_price['bid'] - self._get_slippage()

                # Calculate commission
                commission = volume * self.commission_per_lot

                # Create position
                position = SimulatedPosition(
                    ticket=ticket,
                    symbol=symbol,
                    type='BUY' if order_type == mt5.ORDER_TYPE_BUY else 'SELL',
                    volume=volume,
                    price_open=execution_price,
                    sl=sl,
                    tp=tp,
                    magic=magic,
                    comment=comment,
                    time_open=current_time,
                    commission=commission
                )

                self.positions[ticket] = position
                self.balance -= commission
                self.trade_count += 1

                logger.info(f"Market order filled: {position.type} {volume} @ {execution_price:.5f}, "
                           f"ticket={ticket}, commission=${commission:.2f}")

                return True, {
                    'retcode': mt5.TRADE_RETCODE_DONE,
                    'deal': ticket,
                    'order': ticket,
                    'volume': volume,
                    'price': execution_price,
                    'comment': comment,
                    'request_id': 0,
                    'retcode_external': 0,
                }

            # Pending order
            elif action == mt5.TRADE_ACTION_PENDING:
                expiration = datetime.fromtimestamp(order_request.get('expiration', 0), tz=timezone.utc)

                order = SimulatedOrder(
                    ticket=ticket,
                    symbol=symbol,
                    type=self._get_order_type_name(order_type),
                    volume=volume,
                    price=price,
                    sl=sl,
                    tp=tp,
                    magic=magic,
                    comment=comment,
                    time_setup=current_time,
                    expiration=expiration
                )

                self.orders[ticket] = order

                logger.info(f"Pending order placed: {order.type} {volume} @ {price:.5f}, ticket={ticket}")

                return True, {
                    'retcode': mt5.TRADE_RETCODE_DONE,
                    'deal': 0,
                    'order': ticket,
                    'volume': volume,
                    'price': price,
                    'comment': comment,
                    'request_id': 0,
                    'retcode_external': 0,
                }

            else:
                return False, {'retcode': mt5.TRADE_RETCODE_INVALID, 'error': 'Invalid action'}

        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return False, {'retcode': mt5.TRADE_RETCODE_ERROR, 'error': str(e)}

    def close_position(self, ticket: int, current_price: Dict,
                      current_time: datetime) -> bool:
        """Close a position"""
        try:
            if ticket not in self.positions:
                logger.warning(f"Position {ticket} not found")
                return True  # Already closed

            position = self.positions[ticket]

            # Determine close price with slippage
            if position.type == 'BUY':
                close_price = current_price['bid'] - self._get_slippage()
            else:  # SELL
                close_price = current_price['ask'] + self._get_slippage()

            # Calculate profit
            profit = self._calculate_profit(position, close_price)

            # Update balance
            self.balance += profit

            # Record closed trade
            duration = (current_time - position.time_open).total_seconds()
            self.closed_trades.append({
                'ticket': ticket,
                'symbol': position.symbol,
                'type': position.type,
                'volume': position.volume,
                'price_open': position.price_open,
                'price_close': close_price,
                'sl': position.sl,
                'tp': position.tp,
                'profit': profit,
                'commission': position.commission,
                'swap': position.swap,
                'time_open': position.time_open,
                'time_close': current_time,
                'duration_seconds': duration,
                'magic': position.magic,
                'comment': position.comment,
            })

            # Remove position
            del self.positions[ticket]

            logger.info(f"Position closed: ticket={ticket}, profit=${profit:.2f}")

            return True

        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return False

    def cancel_order(self, ticket: int) -> bool:
        """Cancel a pending order"""
        try:
            if ticket not in self.orders:
                logger.warning(f"Order {ticket} not found")
                return True

            order = self.orders[ticket]
            del self.orders[ticket]

            logger.info(f"Order cancelled: ticket={ticket}")
            return True

        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False

    def modify_position(self, ticket: int, sl: Optional[float] = None,
                       tp: Optional[float] = None) -> bool:
        """Modify position SL/TP"""
        try:
            if ticket not in self.positions:
                logger.error(f"Position {ticket} not found")
                return False

            position = self.positions[ticket]

            if sl is not None:
                position.sl = sl
                logger.debug(f"Modified SL for position {ticket}: {sl:.5f}")

            if tp is not None:
                position.tp = tp
                logger.debug(f"Modified TP for position {ticket}: {tp:.5f}")

            return True

        except Exception as e:
            logger.error(f"Error modifying position: {e}")
            return False

    def update_positions(self, current_price: Dict, current_time: datetime):
        """
        Update all positions (profit, check SL/TP)

        Args:
            current_price: Current market price {'bid': x, 'ask': y, 'spread': z}
            current_time: Current simulation time
        """
        try:
            # Update equity and profit for all positions
            total_profit = 0.0

            for ticket, position in list(self.positions.items()):
                # Calculate current profit
                current_market_price = current_price['bid'] if position.type == 'BUY' else current_price['ask']
                position.profit = self._calculate_profit(position, current_market_price)
                total_profit += position.profit

                # CRITICAL FIX: Check SL/TP hits using bar's HIGH/LOW (not just close)
                # This properly models intra-bar execution
                if position.sl > 0 or position.tp > 0:
                    should_close = False
                    close_price = None
                    hit_type = None

                    # Get bar OHLC data if available
                    bar_high = current_price.get('high', current_price.get('ask'))
                    bar_low = current_price.get('low', current_price.get('bid'))

                    if position.type == 'BUY':
                        sl_hit = position.sl > 0 and bar_low <= position.sl
                        tp_hit = position.tp > 0 and bar_high >= position.tp

                        # Conservative modeling: if both hit in same bar, assume SL hit first
                        if sl_hit and tp_hit:
                            should_close = True
                            close_price = position.sl  # Worst case: SL hit
                            hit_type = 'SL (conservative - both hit)'
                            logger.info(f"Position {ticket} - Both SL and TP hit in bar, "
                                      f"conservative: SL={position.sl:.5f}")
                        elif sl_hit:
                            should_close = True
                            close_price = position.sl
                            hit_type = 'SL'
                            logger.info(f"Position {ticket} hit SL: bar_low={bar_low:.5f} <= {position.sl:.5f}")
                        elif tp_hit:
                            should_close = True
                            close_price = position.tp
                            hit_type = 'TP'
                            logger.info(f"Position {ticket} hit TP: bar_high={bar_high:.5f} >= {position.tp:.5f}")

                    else:  # SELL
                        sl_hit = position.sl > 0 and bar_high >= position.sl
                        tp_hit = position.tp > 0 and bar_low <= position.tp

                        # Conservative modeling: if both hit in same bar, assume SL hit first
                        if sl_hit and tp_hit:
                            should_close = True
                            close_price = position.sl  # Worst case: SL hit
                            hit_type = 'SL (conservative - both hit)'
                            logger.info(f"Position {ticket} - Both SL and TP hit in bar, "
                                      f"conservative: SL={position.sl:.5f}")
                        elif sl_hit:
                            should_close = True
                            close_price = position.sl
                            hit_type = 'SL'
                            logger.info(f"Position {ticket} hit SL: bar_high={bar_high:.5f} >= {position.sl:.5f}")
                        elif tp_hit:
                            should_close = True
                            close_price = position.tp
                            hit_type = 'TP'
                            logger.info(f"Position {ticket} hit TP: bar_low={bar_low:.5f} <= {position.tp:.5f}")

                    if should_close:
                        # Create price dict with exact SL/TP price for close
                        close_price_dict = current_price.copy()
                        if position.type == 'BUY':
                            close_price_dict['bid'] = close_price
                        else:
                            close_price_dict['ask'] = close_price
                        self.close_position(ticket, close_price_dict, current_time)

            # Update equity
            self.equity = self.balance + total_profit

        except Exception as e:
            logger.error(f"Error updating positions: {e}")

    def check_pending_orders(self, current_price: Dict, current_time: datetime):
        """Check if any pending orders should be filled"""
        try:
            for ticket, order in list(self.orders.items()):
                should_fill = False
                fill_price = 0.0

                # Check expiration
                if current_time >= order.expiration:
                    logger.info(f"Order {ticket} expired")
                    del self.orders[ticket]
                    continue

                # CRITICAL FIX: Check if price reached order level using bar HIGH/LOW
                # Get bar OHLC data if available
                bar_high = current_price.get('high', current_price.get('ask'))
                bar_low = current_price.get('low', current_price.get('bid'))

                # Check if price reached order level during the bar
                if order.type == 'BUY_LIMIT':
                    # Buy limit fills when ask drops to or below limit price
                    if bar_low <= order.price:
                        should_fill = True
                        fill_price = order.price + self._get_slippage()

                elif order.type == 'SELL_LIMIT':
                    # Sell limit fills when bid rises to or above limit price
                    if bar_high >= order.price:
                        should_fill = True
                        fill_price = order.price - self._get_slippage()

                elif order.type == 'BUY_STOP':
                    # Buy stop fills when ask rises to or above stop price
                    if bar_high >= order.price:
                        should_fill = True
                        fill_price = order.price + self._get_slippage()

                elif order.type == 'SELL_STOP':
                    # Sell stop fills when bid drops to or below stop price
                    if bar_low <= order.price:
                        should_fill = True
                        fill_price = order.price - self._get_slippage()

                if should_fill:
                    # Fill the order
                    commission = order.volume * self.commission_per_lot

                    position = SimulatedPosition(
                        ticket=ticket,
                        symbol=order.symbol,
                        type='BUY' if 'BUY' in order.type else 'SELL',
                        volume=order.volume,
                        price_open=fill_price,
                        sl=order.sl,
                        tp=order.tp,
                        magic=order.magic,
                        comment=order.comment,
                        time_open=current_time,
                        commission=commission
                    )

                    self.positions[ticket] = position
                    self.balance -= commission
                    self.trade_count += 1

                    # Remove order
                    del self.orders[ticket]

                    logger.info(f"Pending order filled: {position.type} {position.volume} @ {fill_price:.5f}, ticket={ticket}")

        except Exception as e:
            logger.error(f"Error checking pending orders: {e}")

    def _calculate_profit(self, position: SimulatedPosition, close_price: float) -> float:
        """Calculate profit for a position"""
        try:
            if position.type == 'BUY':
                price_diff = close_price - position.price_open
            else:  # SELL
                price_diff = position.price_open - close_price

            profit = price_diff * position.volume * self.symbol_info['contract_size']
            profit -= position.commission
            profit -= position.swap

            return profit

        except Exception as e:
            logger.error(f"Error calculating profit: {e}")
            return 0.0

    def _get_slippage(self) -> float:
        """Calculate random slippage"""
        point = self.symbol_info.get('point', 0.01)
        slippage = np.random.uniform(0, self.slippage_pips) * point
        return slippage

    def _get_next_ticket(self) -> int:
        """Get next ticket number"""
        ticket = self.next_ticket
        self.next_ticket += 1
        return ticket

    def _get_order_type_name(self, order_type: int) -> str:
        """Convert MT5 order type to string"""
        type_map = {
            mt5.ORDER_TYPE_BUY: 'BUY',
            mt5.ORDER_TYPE_SELL: 'SELL',
            mt5.ORDER_TYPE_BUY_LIMIT: 'BUY_LIMIT',
            mt5.ORDER_TYPE_SELL_LIMIT: 'SELL_LIMIT',
            mt5.ORDER_TYPE_BUY_STOP: 'BUY_STOP',
            mt5.ORDER_TYPE_SELL_STOP: 'SELL_STOP',
        }
        return type_map.get(order_type, 'UNKNOWN')

    def get_statistics(self) -> Dict:
        """Get trading statistics"""
        if not self.closed_trades:
            return {}

        profits = [t['profit'] for t in self.closed_trades]
        wins = [p for p in profits if p > 0]
        losses = [p for p in profits if p < 0]

        return {
            'total_trades': len(self.closed_trades),
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'win_rate': len(wins) / len(self.closed_trades) * 100 if self.closed_trades else 0,
            'total_profit': sum(wins),
            'total_loss': abs(sum(losses)),
            'net_profit': sum(profits),
            'avg_win': np.mean(wins) if wins else 0,
            'avg_loss': abs(np.mean(losses)) if losses else 0,
            'largest_win': max(wins) if wins else 0,
            'largest_loss': abs(min(losses)) if losses else 0,
            'profit_factor': abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else 0,
            'current_balance': self.balance,
            'current_equity': self.equity,
            'return_pct': (self.balance - self.initial_balance) / self.initial_balance * 100,
        }
