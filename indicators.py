"""
Technical Indicators Module
Implements ICT concepts: Order Blocks, Fair Value Gaps, Market Structure, and standard indicators
"""

import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class Indicators:
    """
    Collection of technical indicators including ICT-specific concepts
    """
    
    @staticmethod
    def ema(df: pd.DataFrame, period: int, column: str = 'close') -> pd.Series:
        """Calculate Exponential Moving Average"""
        try:
            return df[column].ewm(span=period, adjust=False).mean()
        except Exception as e:
            logger.error(f"Error calculating EMA: {e}")
            return pd.Series(index=df.index)
    
    @staticmethod
    def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        try:
            high = df['high']
            low = df['low']
            close = df['close']
            
            # Calculate True Range
            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())
            
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            # Calculate ATR
            atr = tr.rolling(window=period).mean()
            
            # Use EMA for first period
            atr.iloc[period-1] = tr.iloc[:period].mean()
            for i in range(period, len(atr)):
                atr.iloc[i] = (atr.iloc[i-1] * (period - 1) + tr.iloc[i]) / period
            
            return atr
            
        except Exception as e:
            logger.error(f"Error calculating ATR: {e}")
            return pd.Series(index=df.index)
    
    @staticmethod
    def detect_pivots(df: pd.DataFrame, left: int = 5, right: int = 3) -> pd.DataFrame:
        """
        Detect pivot highs and lows
        Returns DataFrame with pivot_high and pivot_low columns
        """
        try:
            pivots = pd.DataFrame(index=df.index)
            pivots['pivot_high'] = np.nan
            pivots['pivot_low'] = np.nan
            
            # Need enough bars
            if len(df) < left + right + 1:
                return pivots
            
            for i in range(left, len(df) - right):
                # Check for pivot high
                is_pivot_high = True
                high_val = df['high'].iloc[i]
                
                # Check left side
                for j in range(1, left + 1):
                    if df['high'].iloc[i - j] >= high_val:
                        is_pivot_high = False
                        break
                
                # Check right side
                if is_pivot_high:
                    for j in range(1, right + 1):
                        if df['high'].iloc[i + j] > high_val:
                            is_pivot_high = False
                            break
                
                if is_pivot_high:
                    #pivots['pivot_high'].iloc[i] = high_val
                    pivots.loc[i, "pivot_high"] = high_val
                
                # Check for pivot low
                is_pivot_low = True
                low_val = df['low'].iloc[i]
                
                # Check left side
                for j in range(1, left + 1):
                    if df['low'].iloc[i - j] <= low_val:
                        is_pivot_low = False
                        break
                
                # Check right side
                if is_pivot_low:
                    for j in range(1, right + 1):
                        if df['low'].iloc[i + j] < low_val:
                            is_pivot_low = False
                            break
                
                if is_pivot_low:
                    #pivots['pivot_low'].iloc[i] = low_val
                    pivots.loc[i, "pivot_low"] = low_val
            
            return pivots
            
        except Exception as e:
            logger.error(f"Error detecting pivots: {e}")
            return pd.DataFrame(index=df.index)
    
    @staticmethod
    def detect_order_blocks(df: pd.DataFrame, lookback: int = 20, 
                           min_body_ratio: float = 0.5) -> List[Dict]:
        """
        Detect Order Blocks (OB) - last bullish/bearish candle before strong move
        
        Returns list of order blocks with metadata
        """
        try:
            order_blocks = []
            
            if len(df) < lookback:
                return order_blocks
            
            # Calculate average body size for reference
            avg_body = df['body'].rolling(window=20, min_periods=5).mean()
            
            for i in range(lookback, len(df) - 1):
                current_close = df['close'].iloc[i]
                current_open = df['open'].iloc[i]
                next_close = df['close'].iloc[i + 1]
                next_open = df['open'].iloc[i + 1]
                current_low = df['low'].iloc[i]
                # Bullish Order Block: Last down candle before strong up move
                if current_close < current_open:  # Down candle
                    # Check for strong bullish move after
                    # Safety check: ensure avg_body is valid and not zero
                    if pd.notna(avg_body.iloc[i]) and avg_body.iloc[i] > 0 and next_close > next_open and \
                       (next_close - next_open) > avg_body.iloc[i] * 1.5:

                        # Calculate move strength (avg_body already checked above)
                        move_strength = abs(next_close - current_low) / avg_body.iloc[i]

                        if move_strength > 2:  # Strong move
                            ob = {
                                'type': 'bullish',
                                'index': i,
                                'time': df.index[i],
                                'high': df['high'].iloc[i],
                                'low': df['low'].iloc[i],
                                'zone_high': current_open,
                                'zone_low': current_close,
                                'strength': move_strength,
                                'body_size': abs(current_close - current_open),
                            }
                            order_blocks.append(ob)

                # Bearish Order Block: Last up candle before strong down move
                elif current_close > current_open:  # Up candle
                    # Check for strong bearish move after
                    # Safety check: ensure avg_body is valid and not zero
                    if pd.notna(avg_body.iloc[i]) and avg_body.iloc[i] > 0 and next_close < next_open and \
                       (next_open - next_close) > avg_body.iloc[i] * 1.5:

                        current_high = df['high'].iloc[i]
                        move_strength = abs(current_high - next_close) / avg_body.iloc[i]
                        
                        if move_strength > 2:  # Strong move
                            ob = {
                                'type': 'bearish',
                                'index': i,
                                'time': df.index[i],
                                'high': df['high'].iloc[i],
                                'low': df['low'].iloc[i],
                                'zone_high': current_close,
                                'zone_low': current_open,
                                'strength': move_strength,
                                'body_size': abs(current_close - current_open),
                            }
                            order_blocks.append(ob)
            
            # Sort by strength and keep only recent strong ones
            order_blocks.sort(key=lambda x: x['strength'], reverse=True)
            
            # Filter out old order blocks (keep only last N bars)
            recent_blocks = []
            current_index = len(df) - 1
            for ob in order_blocks:
                age = current_index - ob['index']
                if age <= lookback:
                    ob['age'] = age
                    recent_blocks.append(ob)
            
            return recent_blocks[:5]  # Return top 5 most recent strong OBs
            
        except Exception as e:
            logger.error(f"Error detecting order blocks: {e}")
            return []
    
    @staticmethod
    def detect_fair_value_gaps(df: pd.DataFrame, min_gap_points: float = 3,
                              point_value: float = 0.01) -> List[Dict]:
        """
        Detect Fair Value Gaps (FVG) - price imbalances between candles
        
        FVG occurs when there's a gap between:
        - Bullish FVG: Low of candle 3 > High of candle 1
        - Bearish FVG: High of candle 3 < Low of candle 1
        """
        try:
            fvgs = []
            
            if len(df) < 3:
                return fvgs

            # Safety check for point_value
            if point_value <= 0:
                logger.warning(f"Invalid point_value: {point_value}, using default 0.01")
                point_value = 0.01

            min_gap_size = min_gap_points * point_value

            for i in range(2, len(df)):
                # Get three consecutive candles
                candle1 = df.iloc[i-2]
                candle2 = df.iloc[i-1]
                candle3 = df.iloc[i]
                
                # Bullish FVG
                if candle3['low'] > candle1['high']:
                    gap_size = candle3['low'] - candle1['high']
                    
                    if gap_size >= min_gap_size:
                        fvg = {
                            'type': 'bullish',
                            'index': i-1,
                            'time': df.index[i-1],
                            'gap_high': candle3['low'],
                            'gap_low': candle1['high'],
                            'gap_size': gap_size,
                            'gap_points': gap_size / point_value,
                            'filled': False,
                        }
                        fvgs.append(fvg)
                
                # Bearish FVG
                elif candle3['high'] < candle1['low']:
                    gap_size = candle1['low'] - candle3['high']
                    
                    if gap_size >= min_gap_size:
                        fvg = {
                            'type': 'bearish',
                            'index': i-1,
                            'time': df.index[i-1],
                            'gap_high': candle1['low'],
                            'gap_low': candle3['high'],
                            'gap_size': gap_size,
                            'gap_points': gap_size / point_value,
                            'filled': False,
                        }
                        fvgs.append(fvg)
            
            # Check if FVGs have been filled
            current_price = df['close'].iloc[-1]
            for fvg in fvgs:
                if fvg['type'] == 'bullish':
                    # Bullish FVG is filled if price comes back down into gap
                    if current_price <= fvg['gap_high']:
                        fvg['filled'] = True
                else:
                    # Bearish FVG is filled if price comes back up into gap
                    if current_price >= fvg['gap_low']:
                        fvg['filled'] = True
            
            # Filter out filled FVGs and old ones
            unfilled_fvgs = []
            current_index = len(df) - 1
            
            for fvg in fvgs:
                if not fvg['filled']:
                    age = current_index - fvg['index']
                    if age <= 50:  # Keep FVGs from last 50 bars
                        fvg['age'] = age
                        unfilled_fvgs.append(fvg)
            
            # Sort by gap size (larger gaps are stronger)
            unfilled_fvgs.sort(key=lambda x: x['gap_size'], reverse=True)
            
            return unfilled_fvgs[:5]  # Return top 5 unfilled FVGs
            
        except Exception as e:
            logger.error(f"Error detecting FVGs: {e}")
            return []
    
    @staticmethod
    def detect_market_structure(df: pd.DataFrame, pivots: pd.DataFrame) -> Dict:
        """
        Detect Market Structure - Higher Highs/Lows (uptrend) or Lower Highs/Lows (downtrend)
        """
        try:
            # Get recent pivots
            recent_highs = pivots['pivot_high'].dropna().tail(4)
            recent_lows = pivots['pivot_low'].dropna().tail(4)
            
            structure = {
                'trend': 'neutral',
                'last_high': None,
                'last_low': None,
                'structure_break': False,
                'choch': False,  # Change of Character
            }
            
            if len(recent_highs) < 2 or len(recent_lows) < 2:
                return structure
            
            # Get last two highs and lows
            last_high = recent_highs.iloc[-1]
            prev_high = recent_highs.iloc[-2]
            last_low = recent_lows.iloc[-1]
            prev_low = recent_lows.iloc[-2]
            
            structure['last_high'] = last_high
            structure['last_low'] = last_low
            
            # Determine trend based on pivot progression
            if last_high > prev_high and last_low > prev_low:
                structure['trend'] = 'bullish'
            elif last_high < prev_high and last_low < prev_low:
                structure['trend'] = 'bearish'
            
            # Check for structure break
            current_price = df['close'].iloc[-1]
            
            if structure['trend'] == 'bullish':
                # Bearish structure break if price breaks below last low
                if current_price < last_low:
                    structure['structure_break'] = True
                    structure['choch'] = True
            elif structure['trend'] == 'bearish':
                # Bullish structure break if price breaks above last high
                if current_price > last_high:
                    structure['structure_break'] = True
                    structure['choch'] = True
            
            return structure
            
        except Exception as e:
            logger.error(f"Error detecting market structure: {e}")
            return {'trend': 'neutral'}
    
    @staticmethod
    def detect_liquidity_sweeps(df: pd.DataFrame, pivots: pd.DataFrame,
                               sweep_points: float = 2, point_value: float = 0.01) -> List[Dict]:
        """
        Detect liquidity sweeps - price briefly exceeding pivot highs/lows
        """
        try:
            sweeps = []
            sweep_distance = sweep_points * point_value
            
            # Get recent pivots
            recent_highs = pivots['pivot_high'].dropna().tail(10)
            recent_lows = pivots['pivot_low'].dropna().tail(10)
            
            # Check last few bars for sweeps
            for i in range(max(0, len(df) - 5), len(df)):
                bar = df.iloc[i]
                
                # Check for sweep of pivot highs
                for idx, pivot_high in recent_highs.items():
                    if bar['high'] > pivot_high and \
                       bar['high'] <= pivot_high + sweep_distance and \
                       bar['close'] < pivot_high:
                        
                        sweep = {
                            'type': 'bearish_sweep',
                            'index': i,
                            'time': df.index[i],
                            'pivot_level': pivot_high,
                            'sweep_high': bar['high'],
                            'sweep_distance': bar['high'] - pivot_high,
                            'rejected': bar['close'] < pivot_high,
                        }
                        sweeps.append(sweep)
                
                # Check for sweep of pivot lows
                for idx, pivot_low in recent_lows.items():
                    if bar['low'] < pivot_low and \
                       bar['low'] >= pivot_low - sweep_distance and \
                       bar['close'] > pivot_low:
                        
                        sweep = {
                            'type': 'bullish_sweep',
                            'index': i,
                            'time': df.index[i],
                            'pivot_level': pivot_low,
                            'sweep_low': bar['low'],
                            'sweep_distance': pivot_low - bar['low'],
                            'rejected': bar['close'] > pivot_low,
                        }
                        sweeps.append(sweep)
            
            return sweeps
            
        except Exception as e:
            logger.error(f"Error detecting liquidity sweeps: {e}")
            return []
    
    @staticmethod
    def calculate_session_levels(df: pd.DataFrame, session_times: Dict) -> Dict:
        """
        Calculate session highs, lows, and midpoints
        """
        try:
            levels = {}
            
            for session_name, times in session_times.items():
                # Filter bars within session
                session_mask = (df.index.hour >= times['start_hour']) & \
                             (df.index.hour < times['end_hour'])
                
                session_bars = df[session_mask]
                
                if len(session_bars) > 0:
                    levels[session_name] = {
                        'high': session_bars['high'].max(),
                        'low': session_bars['low'].min(),
                        'midpoint': (session_bars['high'].max() + session_bars['low'].min()) / 2,
                        'volume': session_bars['tick_volume'].sum() if 'tick_volume' in session_bars else 0,
                    }
            
            return levels
            
        except Exception as e:
            logger.error(f"Error calculating session levels: {e}")
            return {}
    
    @staticmethod
    def validate_indicators(df: pd.DataFrame, required_cols: List[str]) -> bool:
        """
        Validate that DataFrame has required indicator columns and they're not all NaN
        """
        try:
            for col in required_cols:
                if col not in df.columns:
                    logger.error(f"Missing required column: {col}")
                    return False
                
                if df[col].isna().all():
                    logger.error(f"Column {col} is all NaN")
                    return False
            
            # Check if we have enough non-NaN values
            min_valid = 10
            for col in required_cols:
                if df[col].notna().sum() < min_valid:
                    logger.warning(f"Column {col} has less than {min_valid} valid values")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating indicators: {e}")
            return False
    
    @staticmethod
    def rank_zones(order_blocks: List[Dict], fvgs: List[Dict]) -> List[Dict]:
        """
        Rank and combine OB and FVG zones by strength and recency
        """
        try:
            all_zones = []
            
            # Add order blocks with type identifier
            for ob in order_blocks:
                zone = ob.copy()
                zone['zone_type'] = 'OB'
                zone['score'] = ob['strength'] * (1 / (ob['age'] + 1))
                all_zones.append(zone)
            
            # Add FVGs with type identifier
            for fvg in fvgs:
                zone = fvg.copy()
                zone['zone_type'] = 'FVG'
                zone['score'] = fvg['gap_points'] * (1 / (fvg['age'] + 1))
                all_zones.append(zone)
            
            # Sort by score
            all_zones.sort(key=lambda x: x['score'], reverse=True)
            
            return all_zones
            
        except Exception as e:
            logger.error(f"Error ranking zones: {e}")
            return []
