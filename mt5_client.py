"""
MT5 Client Wrapper
Handles all MetaTrader 5 interactions with robust error handling and retry logic
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import time
import logging
from typing import Optional, Dict, List, Tuple, Any
from functools import wraps
import os

logger = logging.getLogger(__name__)


def retry_on_failure(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Decorator for retrying failed MT5 operations with exponential backoff"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            current_delay = delay
            
            while attempt < max_attempts:
                try:
                    result = func(*args, **kwargs)
                    if result is not None or attempt == max_attempts - 1:
                        return result
                except Exception as e:
                    logger.warning(f"{func.__name__} attempt {attempt + 1} failed: {e}")
                    if attempt == max_attempts - 1:
                        raise
                
                time.sleep(current_delay)
                current_delay *= backoff
                attempt += 1
            
            return None
        return wrapper
    return decorator


class MT5Client:
    """
    Wrapper for MT5 operations with connection management,
    error handling, and data validation
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.symbol = config['symbol']
        self.connected = False
        self.symbol_info = None
        self.last_tick = None
        self.connection_attempts = 0
        self.max_reconnect_attempts = config.get('reconnect_attempts', 5)
        self.reconnect_delay = config.get('reconnect_delay', 10)
        
    def initialize(self) -> bool:
        """Initialize MT5 connection with credentials from config or env vars"""
        try:
            # Get credentials from environment variables or config
            login = os.getenv('MT5_LOGIN') or self.config.get('mt5', {}).get('login')
            password = os.getenv('MT5_PASSWORD') or self.config.get('mt5', {}).get('password')
            server = os.getenv('MT5_SERVER') or self.config.get('mt5', {}).get('server')
            path = os.getenv('MT5_PATH') or self.config.get('mt5', {}).get('path')
            
            if not all([login, password, server]):
                logger.error("MT5 credentials not provided")
                return False
            
            # Initialize MT5
            init_params = {}
            if path:
                init_params['path'] = path
                
            if not mt5.initialize(**init_params):
                logger.error(f"MT5 initialize failed: {mt5.last_error()}")
                return False
            
            # Login to account
            if not mt5.login(int(login), password=password, server=server):
                logger.error(f"MT5 login failed: {mt5.last_error()}")
                mt5.shutdown()
                return False
            
            # Verify symbol is available
            if not self._validate_symbol():
                logger.error(f"Symbol {self.symbol} not available")
                return False
            
            self.connected = True
            self.connection_attempts = 0
            logger.info(f"MT5 initialized successfully for {self.symbol}")
            
            # Cache symbol info
            self._update_symbol_info()
            
            return True
            
        except Exception as e:
            logger.error(f"MT5 initialization error: {e}")
            return False
    
    def _validate_symbol(self) -> bool:
        """Validate that the symbol exists and is tradeable"""
        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            return False
        
        if not symbol_info.visible:
            if not mt5.symbol_select(self.symbol, True):
                return False
        
        # Check if trading is allowed
        if not symbol_info.trade_mode & mt5.SYMBOL_TRADE_MODE_FULL:
            logger.warning(f"Limited trading mode for {self.symbol}")
        
        return True
    
    def _update_symbol_info(self):
        """Cache symbol specifications"""
        info = mt5.symbol_info(self.symbol)
        if info:
            self.symbol_info = {
                'point': info.point,
                'digits': info.digits,
                'contract_size': info.trade_contract_size,
                'min_lot': info.volume_min,
                'max_lot': info.volume_max,
                'lot_step': info.volume_step,
                'tick_size': info.trade_tick_size,
                'tick_value': info.trade_tick_value,
                'spread': info.spread,
                'stops_level': info.trade_stops_level,
                'freeze_level': info.trade_freeze_level,
            }
            logger.debug(f"Symbol info updated: {self.symbol_info}")
    
    @retry_on_failure(max_attempts=3)
    def get_bars(self, timeframe: str, count: int) -> Optional[pd.DataFrame]:
        """Get historical bars with error handling"""
        if not self.connected:
            if not self.reconnect():
                return None
        
        try:
            # Convert timeframe string to MT5 constant
            tf_map = {
                'M1': mt5.TIMEFRAME_M1,
                'M5': mt5.TIMEFRAME_M5,
                'M15': mt5.TIMEFRAME_M15,
                'M30': mt5.TIMEFRAME_M30,
                'H1': mt5.TIMEFRAME_H1,
                'H4': mt5.TIMEFRAME_H4,
                'D1': mt5.TIMEFRAME_D1,
            }
            
            timeframe_mt5 = tf_map.get(timeframe)
            if not timeframe_mt5:
                logger.error(f"Invalid timeframe: {timeframe}")
                return None
            
            # Get bars from current position
            rates = mt5.copy_rates_from_pos(self.symbol, timeframe_mt5, 0, count)
            
            if rates is None or len(rates) == 0:
                logger.warning(f"No bars received for {self.symbol} {timeframe}")
                return None
            
            # Convert to DataFrame with proper datetime index
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
            df.set_index('time', inplace=True)
            
            # Add calculated fields
            df['hl2'] = (df['high'] + df['low']) / 2
            df['hlc3'] = (df['high'] + df['low'] + df['close']) / 3
            df['ohlc4'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
            df['body'] = abs(df['close'] - df['open'])
            df['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
            df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting bars: {e}")
            return None
    
    @retry_on_failure(max_attempts=3)
    def get_tick(self) -> Optional[Dict]:
        """Get current tick data"""
        if not self.connected:
            if not self.reconnect():
                return None
        
        try:
            tick = mt5.symbol_info_tick(self.symbol)
            if tick is None:
                return None
            
            tick_data = {
                'time': datetime.fromtimestamp(tick.time, tz=timezone.utc),
                'bid': tick.bid,
                'ask': tick.ask,
                'last': tick.last,
                'volume': tick.volume,
                'spread': (tick.ask - tick.bid) / self.symbol_info['point'] if self.symbol_info and self.symbol_info.get('point', 0) > 0 else 0,
                'time_msc': tick.time_msc,
            }
            
            self.last_tick = tick_data
            return tick_data
            
        except Exception as e:
            logger.error(f"Error getting tick: {e}")
            return None
    
    def get_account_info(self) -> Optional[Dict]:
        """Get account information"""
        if not self.connected:
            return None
        
        try:
            info = mt5.account_info()
            if info is None:
                return None
            
            return {
                'balance': info.balance,
                'equity': info.equity,
                'margin': info.margin,
                'free_margin': info.margin_free,
                'margin_level': info.margin_level,
                'profit': info.profit,
                'currency': info.currency,
                'leverage': info.leverage,
                'limit_orders': info.limit_orders,
            }
            
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            return None
    
    def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get open positions"""
        if not self.connected:
            return []
        
        try:
            if symbol:
                positions = mt5.positions_get(symbol=symbol)
            else:
                positions = mt5.positions_get()
            
            if positions is None:
                return []
            
            return [self._position_to_dict(pos) for pos in positions]
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []
    
    def get_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get pending orders"""
        if not self.connected:
            return []
        
        try:
            if symbol:
                orders = mt5.orders_get(symbol=symbol)
            else:
                orders = mt5.orders_get()
            
            if orders is None:
                return []
            
            return [self._order_to_dict(order) for order in orders]
            
        except Exception as e:
            logger.error(f"Error getting orders: {e}")
            return []
    
    def place_order(self, order_request: Dict) -> Tuple[bool, Dict]:
        """Place an order with comprehensive error handling"""
        if not self.connected:
            return False, {'error': 'Not connected'}
        
        try:
            # Validate order request
            if not self._validate_order_request(order_request):
                return False, {'error': 'Invalid order request'}
            
            # Send order
            result = mt5.order_send(order_request)
            
            if result is None:
                return False, {'error': 'Order send returned None'}
            
            result_dict = {
                'retcode': result.retcode,
                'deal': result.deal,
                'order': result.order,
                'volume': result.volume,
                'price': result.price,
                'comment': result.comment,
                'request_id': result.request_id,
                'retcode_external': result.retcode_external,
            }
            
            # Check result
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                error_msg = self._get_retcode_message(result.retcode)
                logger.error(f"Order failed: {error_msg}")
                result_dict['error'] = error_msg
                return False, result_dict
            
            logger.info(f"Order placed successfully: {result.order}")
            return True, result_dict
            
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return False, {'error': str(e)}
    
    def modify_order(self, ticket: int, sl: float = None, tp: float = None) -> bool:
        """Modify an existing order"""
        if not self.connected:
            return False
        
        try:
            # Get order details
            orders = mt5.orders_get(ticket=ticket)
            if not orders:
                logger.error(f"Order {ticket} not found")
                return False
            
            order = orders[0]
            
            # Build modification request
            request = {
                'action': mt5.TRADE_ACTION_MODIFY,
                'order': ticket,
                'symbol': order.symbol,
                'sl': sl if sl is not None else order.sl,
                'tp': tp if tp is not None else order.tp,
                'price': order.price_open,
                'type_time': order.type_time,
                'expiration': order.expiration,
            }
            
            result = mt5.order_send(request)
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"Order modification failed: {self._get_retcode_message(result.retcode)}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error modifying order: {e}")
            return False
    
    def cancel_order(self, ticket: int) -> bool:
        """Cancel a pending order"""
        if not self.connected:
            return False
        
        try:
            # Get order details
            orders = mt5.orders_get(ticket=ticket)
            if not orders:
                logger.warning(f"Order {ticket} not found")
                return True  # Consider already cancelled
            
            order = orders[0]
            
            # Build cancellation request
            request = {
                'action': mt5.TRADE_ACTION_REMOVE,
                'order': ticket,
                'symbol': order.symbol,
            }
            
            result = mt5.order_send(request)
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"Order cancellation failed: {self._get_retcode_message(result.retcode)}")
                return False
            
            logger.info(f"Order {ticket} cancelled successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False
    
    def close_position(self, ticket: int) -> bool:
        """Close an open position"""
        if not self.connected:
            return False
        
        try:
            # Get position details
            positions = mt5.positions_get(ticket=ticket)
            if not positions:
                logger.warning(f"Position {ticket} not found")
                return True
            
            position = positions[0]
            
            # Determine close type (opposite of position type)
            close_type = mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            
            # Build close request
            request = {
                'action': mt5.TRADE_ACTION_DEAL,
                'symbol': position.symbol,
                'volume': position.volume,
                'type': close_type,
                'position': ticket,
                'magic': self.config.get('magic', 0),
                'comment': 'Close by bot',
            }
            
            result = mt5.order_send(request)
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"Position close failed: {self._get_retcode_message(result.retcode)}")
                return False
            
            logger.info(f"Position {ticket} closed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return False
    
    def reconnect(self) -> bool:
        """Attempt to reconnect to MT5"""
        if self.connection_attempts >= self.max_reconnect_attempts:
            logger.error("Maximum reconnection attempts reached")
            return False
        
        self.connection_attempts += 1
        logger.info(f"Attempting reconnection {self.connection_attempts}/{self.max_reconnect_attempts}")
        
        # Shutdown existing connection
        try:
            mt5.shutdown()
        except:
            pass
        
        time.sleep(self.reconnect_delay)
        
        # Try to reconnect
        if self.initialize():
            logger.info("Reconnection successful")
            return True
        
        return False
    
    def shutdown(self):
        """Shutdown MT5 connection"""
        try:
            mt5.shutdown()
            self.connected = False
            logger.info("MT5 connection closed")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    def _validate_order_request(self, request: Dict) -> bool:
        """Validate order request parameters"""
        required = ['action', 'symbol', 'volume', 'type']
        for field in required:
            if field not in request:
                logger.error(f"Missing required field: {field}")
                return False
        
        # Validate volume
        if self.symbol_info:
            volume = request['volume']
            min_lot = self.symbol_info['min_lot']
            max_lot = self.symbol_info['max_lot']
            lot_step = self.symbol_info['lot_step']
            
            if volume < min_lot or volume > max_lot:
                #logger.error(f"Volume {volume} outside valid range [{min_lot}, {max_lot}]")
                #return False
                logger.info(f"Got volume {volume} placing with 0.01")
                volume = 0.01
            # Round to lot step
            request['volume'] = round(volume / lot_step) * lot_step
        
        return True
    
    def _position_to_dict(self, position) -> Dict:
        """Convert MT5 position to dictionary"""
        return {
            'ticket': position.ticket,
            'symbol': position.symbol,
            'type': 'BUY' if position.type == mt5.ORDER_TYPE_BUY else 'SELL',
            'volume': position.volume,
            'price': position.price_open,
            'sl': position.sl,
            'tp': position.tp,
            'profit': position.profit,
            'swap': position.swap,
            #'commission': position.commission,
            'magic': position.magic,
            'comment': position.comment,
            'time': datetime.fromtimestamp(position.time, tz=timezone.utc),
        }
    
    def _order_to_dict(self, order) -> Dict:
        """Convert MT5 order to dictionary"""
        return {
            'ticket': order.ticket,
            'symbol': order.symbol,
            'type': self._get_order_type_name(order.type),
            'volume': order.volume_current,
            'price': order.price_open,
            'sl': order.sl,
            'tp': order.tp,
            'magic': order.magic,
            'comment': order.comment,
            'time_setup': datetime.fromtimestamp(order.time_setup, tz=timezone.utc),
            'time_expiration': datetime.fromtimestamp(order.time_expiration, tz=timezone.utc) if order.time_expiration else None,
        }
    
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
    
    def _get_retcode_message(self, retcode: int) -> str:
        """Get human-readable message for MT5 return code"""
        messages = {
            mt5.TRADE_RETCODE_REQUOTE: "Requote",
            mt5.TRADE_RETCODE_REJECT: "Request rejected",
            mt5.TRADE_RETCODE_CANCEL: "Request cancelled",
            mt5.TRADE_RETCODE_PLACED: "Order placed",
            mt5.TRADE_RETCODE_DONE: "Request completed",
            mt5.TRADE_RETCODE_DONE_PARTIAL: "Request partially completed",
            mt5.TRADE_RETCODE_ERROR: "Request processing error",
            mt5.TRADE_RETCODE_TIMEOUT: "Request timeout",
            mt5.TRADE_RETCODE_INVALID: "Invalid request",
            mt5.TRADE_RETCODE_INVALID_VOLUME: "Invalid volume",
            mt5.TRADE_RETCODE_INVALID_PRICE: "Invalid price",
            mt5.TRADE_RETCODE_INVALID_STOPS: "Invalid stops",
            mt5.TRADE_RETCODE_TRADE_DISABLED: "Trade disabled",
            mt5.TRADE_RETCODE_MARKET_CLOSED: "Market closed",
            mt5.TRADE_RETCODE_NO_MONEY: "Not enough money",
            mt5.TRADE_RETCODE_PRICE_CHANGED: "Price changed",
            mt5.TRADE_RETCODE_PRICE_OFF: "No quotes",
            mt5.TRADE_RETCODE_INVALID_EXPIRATION: "Invalid expiration",
            mt5.TRADE_RETCODE_ORDER_CHANGED: "Order state changed",
            mt5.TRADE_RETCODE_TOO_MANY_REQUESTS: "Too many requests",
        }
        return messages.get(retcode, f"Unknown error ({retcode})")
