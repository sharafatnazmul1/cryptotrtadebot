"""
Order Manager Module
Handles order construction, placement, modification, and lifecycle management
"""

import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import json

logger = logging.getLogger(__name__)


class OrderManager:
    """
    Manages order lifecycle with safety checks and idempotency
    """
    
    def __init__(self, config: Dict, mt5_client, risk_manager, persistence):
        self.config = config
        self.mt5_client = mt5_client
        self.risk_manager = risk_manager
        self.persistence = persistence
        self.pending_orders = {}
        self.executed_actions = set()
        
    def process_signal(self, signal: Dict) -> Tuple[bool, Dict]:
        """
        Process a trading signal and place order if appropriate
        """
        try:
            # Check idempotency
            action_id = signal.get('action_id')
            if action_id in self.executed_actions:
                logger.info(f"Action {action_id} already executed, skipping")
                return False, {'error': 'Duplicate action'}
            
            # Validate signal
            if not self._validate_signal(signal):
                return False, {'error': 'Invalid signal'}
            
            # Check risk limits
            risk_check = self.risk_manager.check_signal(signal)
            if not risk_check['allowed']:
                logger.warning(f"Risk check failed: {risk_check['reason']}")
                return False, risk_check
            
            # Calculate lot size
            lot_size = self.risk_manager.calculate_lot_size(signal)
            if lot_size <= 0:
                lot_size = 0.01
                #return False, {'error': 'Invalid lot size'}
            
            signal['lot_size'] = lot_size
            
            # Check existing orders
            if not self._check_existing_orders(signal):
                return False, {'error': 'Conflicting orders exist'}
            
            # Build order request
            order_request = self._build_order_request(signal)
            if not order_request:
                return False, {'error': 'Failed to build order request'}
            
            # Persist signal before execution
            self.persistence.save_signal(signal, status='PENDING')
            
            # Place order
            success, result = self.mt5_client.place_order(order_request)
            
            # Update signal status
            if success:
                signal['mt5_order_id'] = result.get('order')
                signal['mt5_retcode'] = result.get('retcode')
                self.persistence.update_signal(signal['action_id'], status='PLACED', mt5_order_id=result.get('order'))
                
                # Track pending order
                self.pending_orders[result['order']] = {
                    'signal': signal,
                    'placed_time': datetime.now(timezone.utc),
                    'expiry_time': datetime.now(timezone.utc) + timedelta(minutes=self.config.get('pending_expiry_min', 20)),
                }
                
                # Mark action as executed
                self.executed_actions.add(action_id)
                
                logger.info(f"Order placed successfully: {result['order']}")
                return True, result
            else:
                self.persistence.update_signal(signal['action_id'], status='FAILED', error=result.get('error'))
                
                # Handle specific error codes
                self._handle_order_error(result, signal)
                
                return False, result
            
        except Exception as e:
            logger.error(f"Error processing signal: {e}")
            return False, {'error': str(e)}
    
    def _validate_signal(self, signal: Dict) -> bool:
        """
        Validate signal has all required fields
        """
        required_fields = ['symbol', 'side', 'entry_price', 'sl_price', 'tp_price']
        
        for field in required_fields:
            if field not in signal:
                logger.error(f"Signal missing required field: {field}")
                return False
        
        # Validate prices are positive
        if signal['entry_price'] <= 0 or signal['sl_price'] <= 0 or signal['tp_price'] <= 0:
            logger.error("Invalid price values in signal")
            return False
        
        # Validate side
        if signal['side'] not in ['BUY', 'SELL']:
            logger.error(f"Invalid side: {signal['side']}")
            return False
        
        return True
    
    def _check_existing_orders(self, signal: Dict) -> bool:
        """
        Check for conflicting existing orders
        """
        try:
            # Get existing orders for symbol
            orders = self.mt5_client.get_orders(symbol=signal['symbol'])
            positions = self.mt5_client.get_positions(symbol=signal['symbol'])
            
            # Count pending orders
            pending_count = len([o for o in orders if o.get('magic') == self.config.get('magic', 0)])
            max_pending = self.config.get('max_pending', 2)
            
            if pending_count >= max_pending:
                logger.info(f"Maximum pending orders reached: {pending_count} >= {max_pending}")
                return False
            
            # Count open positions
            position_count = len([p for p in positions if p.get('magic') == self.config.get('magic', 0)])
            max_concurrent = self.config.get('max_concurrent_trades', 3)
            
            if position_count >= max_concurrent:
                logger.info(f"Maximum concurrent trades reached: {position_count} >= {max_concurrent}")
                return False
            
            # Check for duplicate pending orders at similar price
            for order in orders:
                if order.get('magic') == self.config.get('magic', 0):
                    price_diff = abs(order['price'] - signal['entry_price'])
                    
                    # If order at very similar price exists, skip
                    if price_diff < signal.get('atr', 10) * 0.2:
                        logger.info(f"Similar pending order exists at {order['price']:.5f}")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking existing orders: {e}")
            return False
    
    def _build_order_request(self, signal: Dict) -> Optional[Dict]:
        """
        Build MT5 order request from signal
        """
        try:
            # Determine order type based on side and current price
            tick = self.mt5_client.get_tick()
            if not tick:
                return None
            
            current_price = tick['ask'] if signal['side'] == 'BUY' else tick['bid']
            
            # Determine if limit or stop order
            if signal['side'] == 'BUY':
                if signal['entry_price'] < current_price:
                    order_type = mt5.ORDER_TYPE_BUY_LIMIT
                else:
                    order_type = mt5.ORDER_TYPE_BUY_STOP
            else:
                if signal['entry_price'] > current_price:
                    order_type = mt5.ORDER_TYPE_SELL_LIMIT
                else:
                    order_type = mt5.ORDER_TYPE_SELL_STOP
            
            # Calculate expiration time
            expiry_minutes = self.config.get('pending_expiry_min', 20)
            expiration = datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)
            expiration_timestamp = int(expiration.timestamp())
            
            # Build request
            request = {
                'action': mt5.TRADE_ACTION_PENDING,
                'symbol': signal['symbol'],
                'volume': signal['lot_size'],
                'type': order_type,
                'price': signal['entry_price'],
                'sl': signal['sl_price'],
                'tp': signal['tp_price'],
                'deviation': 10,  # Max deviation in points
                'magic': self.config.get('magic', 0),
                'comment': f"ICT_{signal.get('zone_type', 'NA')}_{signal.get('action_id', '')[:8]}",
                'type_time': mt5.ORDER_TIME_SPECIFIED,
                'expiration': expiration_timestamp,
            }
            
            logger.debug(f"Built order request: {request}")
            return request
            
        except Exception as e:
            logger.error(f"Error building order request: {e}")
            return None
    
    def _handle_order_error(self, result: Dict, signal: Dict):
        """
        Handle specific order error codes
        """
        retcode = result.get('retcode')
        
        if retcode == mt5.TRADE_RETCODE_INVALID_PRICE:
            logger.error("Invalid price - may need to adjust for broker requirements")
            # Could implement price adjustment logic here
            
        elif retcode == mt5.TRADE_RETCODE_NO_MONEY:
            logger.error("Insufficient funds - reduce lot size or wait")
            # Could notify risk manager to reduce exposure
            
        elif retcode == mt5.TRADE_RETCODE_MARKET_CLOSED:
            logger.error("Market closed")
            
        elif retcode == mt5.TRADE_RETCODE_INVALID_STOPS:
            logger.error("Invalid stop levels - check broker requirements")
            
        elif retcode == mt5.TRADE_RETCODE_TOO_MANY_REQUESTS:
            logger.warning("Too many requests - implement rate limiting")
    
    def manage_pending_orders(self):
        """
        Manage existing pending orders - check expiry, invalidation, etc.
        """
        try:
            current_time = datetime.now(timezone.utc)
            orders_to_cancel = []
            
            # Get current orders from broker
            broker_orders = self.mt5_client.get_orders(symbol=self.config['symbol'])
            broker_order_ids = {order['ticket'] for order in broker_orders}
            
            # Check tracked pending orders
            for order_id, order_data in list(self.pending_orders.items()):
                # Check if order still exists at broker
                if order_id not in broker_order_ids:
                    # Order filled or cancelled externally
                    logger.info(f"Order {order_id} no longer pending")
                    del self.pending_orders[order_id]
                    continue
                
                # Check expiry
                if current_time > order_data['expiry_time']:
                    logger.info(f"Order {order_id} expired")
                    orders_to_cancel.append(order_id)
                    continue
                
                # Check if signal conditions still valid
                signal = order_data['signal']
                if not self._is_signal_still_valid(signal):
                    logger.info(f"Signal conditions for order {order_id} no longer valid")
                    orders_to_cancel.append(order_id)
            
            # Cancel invalid orders
            for order_id in orders_to_cancel:
                if self.mt5_client.cancel_order(order_id):
                    if order_id in self.pending_orders:
                        signal = self.pending_orders[order_id]['signal']
                        self.persistence.update_signal(signal['action_id'], status='CANCELLED')
                        del self.pending_orders[order_id]
            
        except Exception as e:
            logger.error(f"Error managing pending orders: {e}")
    
    def _is_signal_still_valid(self, signal: Dict) -> bool:
        """
        Check if signal conditions are still valid
        """
        try:
            # Get current market data
            tick = self.mt5_client.get_tick()
            if not tick:
                return True  # Assume valid if can't check
            
            current_price = tick['ask'] if signal['side'] == 'BUY' else tick['bid']
            
            # Check if price has moved too far from entry
            max_distance = signal.get('atr', 10) * 3  # 3 ATRs away
            distance = abs(current_price - signal['entry_price'])
            
            if distance > max_distance:
                logger.info(f"Price moved too far from entry: {distance:.5f} > {max_distance:.5f}")
                return False
            
            # Check if spread is still acceptable
            if tick['spread'] > self.config.get('max_spread', 8.0) * 1.5:
                logger.info(f"Spread too high: {tick['spread']}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking signal validity: {e}")
            return True
    
    def close_all_positions(self, reason: str = "Manual close"):
        """
        Emergency close all positions
        """
        try:
            positions = self.mt5_client.get_positions(symbol=self.config['symbol'])
            
            for position in positions:
                if position.get('magic') == self.config.get('magic', 0):
                    logger.info(f"Closing position {position['ticket']}: {reason}")
                    self.mt5_client.close_position(position['ticket'])
            
        except Exception as e:
            logger.error(f"Error closing all positions: {e}")
    
    def cancel_all_pending(self, reason: str = "Manual cancel"):
        """
        Cancel all pending orders
        """
        try:
            orders = self.mt5_client.get_orders(symbol=self.config['symbol'])
            
            for order in orders:
                if order.get('magic') == self.config.get('magic', 0):
                    logger.info(f"Cancelling order {order['ticket']}: {reason}")
                    self.mt5_client.cancel_order(order['ticket'])
            
            # Clear tracking
            self.pending_orders.clear()
            
        except Exception as e:
            logger.error(f"Error cancelling all pending orders: {e}")
    
    def get_status(self) -> Dict:
        """
        Get current order manager status
        """
        try:
            positions = self.mt5_client.get_positions(symbol=self.config['symbol'])
            orders = self.mt5_client.get_orders(symbol=self.config['symbol'])
            
            # Filter by magic number
            my_positions = [p for p in positions if p.get('magic') == self.config.get('magic', 0)]
            my_orders = [o for o in orders if o.get('magic') == self.config.get('magic', 0)]
            
            # Calculate total exposure
            total_volume = sum(p['volume'] for p in my_positions)
            total_profit = sum(p.get('profit', 0) for p in my_positions)
            
            return {
                'open_positions': len(my_positions),
                'pending_orders': len(my_orders),
                'tracked_pending': len(self.pending_orders),
                'total_volume': total_volume,
                'total_profit': total_profit,
                'executed_actions': len(self.executed_actions),
            }
            
        except Exception as e:
            logger.error(f"Error getting order manager status: {e}")
            return {}
