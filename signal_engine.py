"""
Signal Engine Module
Implements ICT trading heuristics and multi-timeframe analysis
"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Tuple
import logging
import hashlib
import json

from indicators import Indicators

logger = logging.getLogger(__name__)


class SignalEngine:
    """
    Generates trading signals based on ICT concepts and multi-timeframe analysis
    """
    
    def __init__(self, config: Dict, mt5_client):
        self.config = config
        self.mt5_client = mt5_client
        self.indicators = Indicators()
        self.last_signal_time = None
        self.signal_history = []
        
    def analyze(self) -> Optional[Dict]:
        """
        Main analysis method - performs multi-timeframe analysis and generates signals
        """
        try:
            # Get multi-timeframe data
            htf_data = self.mt5_client.get_bars(self.config['timeframes']['high'], 100)
            mtf_data = self.mt5_client.get_bars(self.config['timeframes']['med'], 100)
            ltf_data = self.mt5_client.get_bars(self.config['timeframes']['low'], 50)
            
            if htf_data is None or mtf_data is None:
                logger.warning("Failed to get necessary timeframe data")
                return None
            
            # Calculate indicators on each timeframe
            htf_analysis = self._analyze_timeframe(htf_data, 'high')
            mtf_analysis = self._analyze_timeframe(mtf_data, 'medium')
            ltf_analysis = self._analyze_timeframe(ltf_data, 'low') if ltf_data is not None else None
            
            # Check market conditions
            if not self._check_market_conditions():
                return None
            
            # Generate signal based on multi-timeframe confluence
            signal = self._generate_signal(htf_analysis, mtf_analysis, ltf_analysis)
            
            if signal:
                # Add unique action_id for idempotency
                signal['timestamp'] = datetime.now(timezone.utc)
                signal['action_id'] = self._generate_action_id(signal)
                
                
                # Check if signal is duplicate
                if not self._is_duplicate_signal(signal):
                    self.signal_history.append(signal)
                    self.last_signal_time = signal['timestamp']
                    return signal
            
            return None
            
        except Exception as e:
            logger.error(f"Error in signal analysis: {e}")
            return None
    
    def _analyze_timeframe(self, df: pd.DataFrame, timeframe: str) -> Dict:
        """
        Analyze a single timeframe and extract key information
        """
        try:
            analysis = {
                'timeframe': timeframe,
                'trend': 'neutral',
                'ema': None,
                'atr': None,
                'pivots': None,
                'order_blocks': [],
                'fvgs': [],
                'market_structure': {},
                'liquidity_sweeps': [],
            }
            
            if len(df) < 30:
                return analysis
            
            # Calculate EMA
            ema_period = self.config.get('ema_high', 21)
            df['ema'] = self.indicators.ema(df, ema_period)
            analysis['ema'] = df['ema'].iloc[-1]
            
            # Calculate ATR
            atr_period = self.config.get('atr_period', 14)
            df['atr'] = self.indicators.atr(df, atr_period)
            analysis['atr'] = df['atr'].iloc[-1]
            
            # Detect pivots
            pivot_left = self.config.get('pivot_left', 5)
            pivot_right = self.config.get('pivot_right', 3)
            pivots = self.indicators.detect_pivots(df, pivot_left, pivot_right)
            analysis['pivots'] = pivots
            
            # Determine trend
            current_price = df['close'].iloc[-1]
            if current_price > analysis['ema']:
                analysis['trend'] = 'bullish'
            elif current_price < analysis['ema']:
                analysis['trend'] = 'bearish'
            
            # Detect Order Blocks
            if timeframe in ['medium', 'low']:
                ob_lookback = self.config.get('ob_lookback_bars', 20)
                analysis['order_blocks'] = self.indicators.detect_order_blocks(df, ob_lookback)
            
            # Detect Fair Value Gaps
            if timeframe in ['medium', 'low']:
                min_fvg_points = self.config.get('fvg_min_size_points', 3)
                point_value = self.mt5_client.symbol_info['point'] if self.mt5_client.symbol_info else 0.01
                analysis['fvgs'] = self.indicators.detect_fair_value_gaps(df, min_fvg_points, point_value)
            
            # Detect Market Structure
            analysis['market_structure'] = self.indicators.detect_market_structure(df, pivots)
            
            # Detect Liquidity Sweeps
            if timeframe == 'medium':
                sweep_points = self.config.get('liquidity_sweep_points', 2)
                point_value = self.mt5_client.symbol_info['point'] if self.mt5_client.symbol_info else 0.01
                analysis['liquidity_sweeps'] = self.indicators.detect_liquidity_sweeps(
                    df, pivots, sweep_points, point_value
                )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing timeframe {timeframe}: {e}")
            return {}
    
    def _check_market_conditions(self) -> bool:
        """
        Check if market conditions are suitable for trading
        """
        try:
            # Get current tick
            tick = self.mt5_client.get_tick()
            if not tick:
                return False
            
            # Check spread
            max_spread = self.config.get('max_spread', 200.0)
            if tick['spread'] > max_spread:
                logger.info(f"Spread too high: {tick['spread']} > {max_spread}")
                return False
            
            # Check trading sessions
            current_time = datetime.now(timezone.utc)
            enabled_sessions = self.config.get('sessions', {}).get('enabled_sessions', [])
            
            if enabled_sessions:
                in_session = False
                for session in enabled_sessions:
                    session_config = self.config['sessions'].get(session, {})
                    if self._is_in_session(current_time, session_config):
                        in_session = True
                        break
                
                if not in_session:
                    logger.debug("Outside of enabled trading sessions")
                    return False
            
            # Check if we have recent signal (avoid over-trading)
            if self.last_signal_time:
                time_since_signal = (current_time - self.last_signal_time).total_seconds()
                min_signal_interval = 60  # Minimum 1 minute between signals
                if time_since_signal < min_signal_interval:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking market conditions: {e}")
            return False
    
    def _is_in_session(self, current_time: datetime, session_config: Dict) -> bool:
        """
        Check if current time is within trading session
        """
        try:
            if not session_config:
                return True
            
            start_str = session_config.get('start', '00:00')
            end_str = session_config.get('end', '23:59')
            
            start_hour, start_min = map(int, start_str.split(':'))
            end_hour, end_min = map(int, end_str.split(':'))
            
            current_minutes = current_time.hour * 60 + current_time.minute
            start_minutes = start_hour * 60 + start_min
            end_minutes = end_hour * 60 + end_min
            
            # Handle sessions that cross midnight
            if start_minutes <= end_minutes:
                return start_minutes <= current_minutes <= end_minutes
            else:
                return current_minutes >= start_minutes or current_minutes <= end_minutes
            
        except Exception as e:
            logger.error(f"Error checking session: {e}")
            return True
    
    def _generate_signal(self, htf: Dict, mtf: Dict, ltf: Optional[Dict]) -> Optional[Dict]:
        """
        Generate trading signal based on multi-timeframe confluence
        """
        try:
            # Required elements for signal
            if not htf.get('atr') or not mtf.get('atr'):
                logger.debug("ATR not available")
                return None
            
            # Get current price
            tick = self.mt5_client.get_tick()
            if not tick:
                return None
            
            current_price = tick['ask'] if htf['trend'] == 'bullish' else tick['bid']
            
            # Initialize signal scoring
            signal_score = 0
            reason_tags = []
            
            # HTF trend alignment (weight: 3)
            htf_trend = htf.get('trend', 'neutral')
            if htf_trend != 'neutral':
                signal_score += 3
                reason_tags.append(f'HTF_{htf_trend}')
            
            # Market structure alignment (weight: 2)
            ms = mtf.get('market_structure', {})
            if ms.get('trend') == htf_trend:
                signal_score += 2
                reason_tags.append('MS_aligned')
            
            # Check for structure break
            if ms.get('choch'):
                signal_score += 2
                reason_tags.append('CHOCH')
            
            # Find best zone (OB or FVG)
            all_zones = self.indicators.rank_zones(
                mtf.get('order_blocks', []),
                mtf.get('fvgs', [])
            )
            
            if not all_zones:
                logger.debug("No zones found")
                return None
            
            # Get best zone matching trend
            best_zone = None
            for zone in all_zones:
                if htf_trend == 'bullish' and zone.get('type') in ['bullish', 'bullish']:
                    best_zone = zone
                    break
                elif htf_trend == 'bearish' and zone.get('type') in ['bearish', 'bearish']:
                    best_zone = zone
                    break
            
            if not best_zone:
                logger.debug("No zone matching trend")
                return None
            
            # Add zone score
            if best_zone['zone_type'] == 'OB':
                signal_score += 3
                reason_tags.append('Order_Block')
            else:
                signal_score += 2
                reason_tags.append('FVG')
            
            # Check for liquidity sweep (weight: 2)
            sweeps = mtf.get('liquidity_sweeps', [])
            for sweep in sweeps:
                if htf_trend == 'bullish' and sweep['type'] == 'bullish_sweep':
                    signal_score += 2
                    reason_tags.append('Liquidity_Sweep')
                    break
                elif htf_trend == 'bearish' and sweep['type'] == 'bearish_sweep':
                    signal_score += 2
                    reason_tags.append('Liquidity_Sweep')
                    break
            
            # Minimum score threshold
            min_score = 5
            if signal_score < min_score:
                logger.debug(f"Signal score too low: {signal_score} < {min_score}")
                return None
            
            # Calculate entry, stop loss, and take profit
            atr = mtf['atr']
            entry_offset = atr * self.config.get('atr_entry_mult', 0.4)
            sl_distance = atr * self.config.get('sl_atr_mult', 1.6)
            tp_distance = atr * self.config.get('tp_atr_mult', 2.8)
            
            if htf_trend == 'bullish':
                # For bullish signal
                if best_zone['zone_type'] == 'OB':
                    entry_price = best_zone['zone_high'] - entry_offset
                else:  # FVG
                    entry_price = best_zone['gap_high'] - entry_offset
                
                sl_price = entry_price - sl_distance
                tp_price = entry_price + tp_distance
                side = 'BUY'
                
            else:  # bearish
                # For bearish signal
                if best_zone['zone_type'] == 'OB':
                    entry_price = best_zone['zone_low'] + entry_offset
                else:  # FVG
                    entry_price = best_zone['gap_low'] + entry_offset
                
                sl_price = entry_price + sl_distance
                tp_price = entry_price - tp_distance
                side = 'SELL'
            
            # Calculate risk-reward ratio
            risk = abs(entry_price - sl_price)
            reward = abs(tp_price - entry_price)
            rr_ratio = reward / risk if risk > 0 else 0
            
            # Check minimum RR ratio
            min_rr = self.config.get('min_rr', 1.5)
            if rr_ratio < min_rr:
                logger.debug(f"RR ratio too low: {rr_ratio:.2f} < {min_rr}")
                return None
            
            # Round prices to symbol digits
            if self.mt5_client.symbol_info:
                digits = self.mt5_client.symbol_info['digits']
                entry_price = round(entry_price, digits)
                sl_price = round(sl_price, digits)
                tp_price = round(tp_price, digits)
            
            signal = {
                'symbol': self.config['symbol'],
                'side': side,
                'entry_price': entry_price,
                'sl_price': sl_price,
                'tp_price': tp_price,
                'atr': atr,
                'htf_trend': htf_trend,
                'mtf_trend': mtf.get('market_structure', {}).get('trend', 'neutral'),
                'zone_type': best_zone['zone_type'],
                'zone_data': best_zone,
                'reason_tags': reason_tags,
                'signal_score': signal_score,
                'rr_ratio': rr_ratio,
                'current_price': current_price,
                'distance_to_entry': abs(current_price - entry_price),
            }
            
            logger.info(f"Signal generated: {side} at {entry_price:.5f}, "
                       f"SL: {sl_price:.5f}, TP: {tp_price:.5f}, "
                       f"Score: {signal_score}, RR: {rr_ratio:.2f}")
            
            return signal
            
        except Exception as e:
            logger.error(f"Error generating signal: {e}")
            return None
    
    def _generate_action_id(self, signal: Dict) -> str:
        """
        Generate unique action ID for idempotency
        """
        try:
            # Create unique string from signal parameters
            unique_string = f"{self.config['symbol']}_{signal['side']}_{signal['entry_price']:.5f}_{signal['timestamp']}"
            
            # Generate hash
            action_id = hashlib.sha256(unique_string.encode()).hexdigest()[:16]
            
            return action_id
            
        except Exception as e:
            logger.error(f"Error generating action ID: {e}")
            return datetime.now().strftime("%Y%m%d%H%M%S")
    
    def _is_duplicate_signal(self, signal: Dict) -> bool:
        """
        Check if signal is duplicate of recent signal
        """
        try:
            # Check last N signals
            check_count = 10
            recent_signals = self.signal_history[-check_count:] if len(self.signal_history) > check_count else self.signal_history
            
            for prev_signal in recent_signals:
                # Check if same side and similar price
                if prev_signal['side'] == signal['side']:
                    price_diff = abs(prev_signal['entry_price'] - signal['entry_price'])
                    
                    # Consider duplicate if price difference is less than 1 ATR
                    if price_diff < signal['atr']:
                        time_diff = (signal['timestamp'] - prev_signal['timestamp']).total_seconds()
                        
                        # If within last 30 minutes, consider duplicate
                        if time_diff < 1800:
                            logger.debug(f"Duplicate signal detected: {signal['action_id']}")
                            return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking duplicate signal: {e}")
            return False
    
    def validate_signal(self, signal: Dict) -> bool:
        """
        Final validation of signal before execution
        """
        try:
            # Get current tick
            tick = self.mt5_client.get_tick()
            if not tick:
                return False
            
            # Check if entry price is at minimum distance from current price
            current_price = tick['ask'] if signal['side'] == 'BUY' else tick['bid']
            min_distance_points = self.config.get('min_distance_points', 6)
            
            if self.mt5_client.symbol_info:
                point = self.mt5_client.symbol_info['point']
                min_distance = min_distance_points * point
                
                distance = abs(current_price - signal['entry_price'])
                if distance < min_distance:
                    logger.info(f"Entry too close to current price: {distance:.5f} < {min_distance:.5f}")
                    return False
            
            # Check stops level
            if self.mt5_client.symbol_info:
                stops_level = self.mt5_client.symbol_info.get('stops_level', 0)
                if stops_level > 0:
                    stops_distance = stops_level * self.mt5_client.symbol_info['point']
                    
                    sl_distance = abs(signal['entry_price'] - signal['sl_price'])
                    tp_distance = abs(signal['entry_price'] - signal['tp_price'])
                    
                    if sl_distance < stops_distance or tp_distance < stops_distance:
                        logger.warning(f"SL/TP violates stops level: {stops_level}")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating signal: {e}")
            return False
