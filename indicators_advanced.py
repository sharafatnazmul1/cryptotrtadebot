"""
Advanced SMC/ICT Indicators Module
Implements professional hedge fund-grade Smart Money Concepts
"""

import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime, time
import logging

logger = logging.getLogger(__name__)


@dataclass
class PremiumDiscountZone:
    """Premium/Discount zone based on 50% equilibrium"""
    equilibrium: float
    premium_start: float  # 50%
    premium_end: float    # 100%
    discount_start: float # 0%
    discount_end: float   # 50%
    ote_buy_high: float   # 79% retracement
    ote_buy_low: float    # 62% retracement
    ote_sell_high: float  # 62% retracement (from bottom)
    ote_sell_low: float   # 79% retracement (from bottom)


@dataclass
class LiquidityPool:
    """Liquidity pool at equal highs/lows"""
    level: float
    type: str  # 'buyside' or 'sellside'
    touches: int
    strength: float
    last_touch_time: datetime
    swept: bool = False


@dataclass
class OrderBlock:
    """Enhanced Order Block with institutional context"""
    type: str  # 'bullish', 'bearish', 'breaker', 'mitigation'
    zone_high: float
    zone_low: float
    time: datetime
    index: int
    strength: float
    tested: bool = False
    broken: bool = False
    mitigation_count: int = 0


@dataclass
class MarketStructure:
    """Enhanced market structure with BOS and CHoCH"""
    trend: str  # 'bullish', 'bearish', 'neutral'
    last_high: float
    last_low: float
    bos: bool  # Break of Structure
    choch: bool  # Change of Character
    mss: bool  # Market Structure Shift
    swing_high: float
    swing_low: float


class AdvancedSMCIndicators:
    """
    Professional hedge fund-grade SMC/ICT indicators
    Based on institutional order flow and smart money concepts
    """

    @staticmethod
    def calculate_premium_discount(high: float, low: float) -> PremiumDiscountZone:
        """
        Calculate Premium/Discount zones based on range
        Premium = above 50% (selling area)
        Discount = below 50% (buying area)
        OTE = Optimal Trade Entry (62-79% Fibonacci)
        """
        try:
            range_size = high - low
            equilibrium = low + (range_size * 0.5)

            return PremiumDiscountZone(
                equilibrium=equilibrium,
                premium_start=equilibrium,
                premium_end=high,
                discount_start=low,
                discount_end=equilibrium,
                # OTE zones for buy (discount retracement)
                ote_buy_low=low + (range_size * 0.62),
                ote_buy_high=low + (range_size * 0.79),
                # OTE zones for sell (premium retracement from top)
                ote_sell_high=high - (range_size * 0.62),
                ote_sell_low=high - (range_size * 0.79),
            )
        except Exception as e:
            logger.error(f"Error calculating premium/discount: {e}")
            return None

    @staticmethod
    def detect_liquidity_pools(df: pd.DataFrame, tolerance_pct: float = 0.001) -> List[LiquidityPool]:
        """
        Detect liquidity pools at equal highs/lows
        These are areas where stops are likely clustered
        """
        try:
            pools = []

            # Find pivot highs
            for i in range(5, len(df) - 5):
                current_high = df['high'].iloc[i]

                # Safety check: skip if current_high is 0 or invalid
                if current_high <= 0:
                    continue

                # Look for equal highs (within tolerance)
                equal_count = 1
                for j in range(i - 5, i):
                    if abs(df['high'].iloc[j] - current_high) / current_high < tolerance_pct:
                        equal_count += 1

                for j in range(i + 1, min(i + 6, len(df))):
                    if abs(df['high'].iloc[j] - current_high) / current_high < tolerance_pct:
                        equal_count += 1

                if equal_count >= 2:  # At least 2 equal highs
                    # Check if already swept
                    swept = any(df['high'].iloc[i+1:] > current_high)

                    # Safety check for strength calculation
                    df_remaining = len(df) - i
                    strength = equal_count * (1.0 / df_remaining) if df_remaining > 0 else 0

                    pool = LiquidityPool(
                        level=current_high,
                        type='buyside',
                        touches=equal_count,
                        strength=strength,
                        last_touch_time=df.index[i],
                        swept=swept
                    )
                    pools.append(pool)

            # Find pivot lows
            for i in range(5, len(df) - 5):
                current_low = df['low'].iloc[i]

                # Safety check: skip if current_low is 0 or invalid
                if current_low <= 0:
                    continue

                equal_count = 1
                for j in range(i - 5, i):
                    if abs(df['low'].iloc[j] - current_low) / current_low < tolerance_pct:
                        equal_count += 1

                for j in range(i + 1, min(i + 6, len(df))):
                    if abs(df['low'].iloc[j] - current_low) / current_low < tolerance_pct:
                        equal_count += 1

                if equal_count >= 2:
                    swept = any(df['low'].iloc[i+1:] < current_low)

                    # Safety check for strength calculation
                    df_remaining = len(df) - i
                    strength = equal_count * (1.0 / df_remaining) if df_remaining > 0 else 0

                    pool = LiquidityPool(
                        level=current_low,
                        type='sellside',
                        touches=equal_count,
                        strength=strength,
                        last_touch_time=df.index[i],
                        swept=swept
                    )
                    pools.append(pool)

            # Sort by strength
            pools.sort(key=lambda x: x.strength, reverse=True)
            return pools[:10]  # Return top 10

        except Exception as e:
            logger.error(f"Error detecting liquidity pools: {e}")
            return []

    @staticmethod
    def detect_bos_choch(df: pd.DataFrame) -> MarketStructure:
        """
        Detect Break of Structure (BOS) and Change of Character (CHoCH)
        BOS = trend continuation (higher high in uptrend, lower low in downtrend)
        CHoCH = potential reversal (market structure shift)
        """
        try:
            if len(df) < 20:
                return MarketStructure('neutral', 0, 0, False, False, False, 0, 0)

            # Find swing highs and lows
            swing_highs = []
            swing_lows = []

            for i in range(10, len(df) - 10):
                # Swing high
                if df['high'].iloc[i] == df['high'].iloc[i-10:i+11].max():
                    swing_highs.append((i, df['high'].iloc[i]))

                # Swing low
                if df['low'].iloc[i] == df['low'].iloc[i-10:i+11].min():
                    swing_lows.append((i, df['low'].iloc[i]))

            if len(swing_highs) < 2 or len(swing_lows) < 2:
                return MarketStructure('neutral', 0, 0, False, False, False, 0, 0)

            # Get last two swing highs and lows
            last_high = swing_highs[-1][1]
            prev_high = swing_highs[-2][1]
            last_low = swing_lows[-1][1]
            prev_low = swing_lows[-2][1]

            current_price = df['close'].iloc[-1]

            # Determine trend
            if last_high > prev_high and last_low > prev_low:
                trend = 'bullish'
                # BOS = new higher high
                bos = current_price > last_high
                # CHoCH = break below last higher low
                choch = current_price < last_low
                mss = choch  # MSS happens with CHoCH

            elif last_high < prev_high and last_low < prev_low:
                trend = 'bearish'
                # BOS = new lower low
                bos = current_price < last_low
                # CHoCH = break above last lower high
                choch = current_price > last_high
                mss = choch

            else:
                trend = 'neutral'
                bos = False
                choch = False
                mss = False

            return MarketStructure(
                trend=trend,
                last_high=last_high,
                last_low=last_low,
                bos=bos,
                choch=choch,
                mss=mss,
                swing_high=swing_highs[-1][1],
                swing_low=swing_lows[-1][1]
            )

        except Exception as e:
            logger.error(f"Error detecting BOS/CHoCH: {e}")
            return MarketStructure('neutral', 0, 0, False, False, False, 0, 0)

    @staticmethod
    def detect_breaker_blocks(df: pd.DataFrame, order_blocks: List[OrderBlock]) -> List[OrderBlock]:
        """
        Detect Breaker Blocks (failed order blocks that become supply/demand zones)
        When bullish OB is broken to downside, it becomes bearish breaker
        When bearish OB is broken to upside, it becomes bullish breaker
        """
        try:
            breakers = []

            for ob in order_blocks:
                if ob.type == 'bullish' and not ob.broken:
                    # Check if price broke below this OB
                    ob_index = ob.index
                    for i in range(ob_index + 1, len(df)):
                        if df['close'].iloc[i] < ob.zone_low:
                            # OB broken, becomes bearish breaker
                            breaker = OrderBlock(
                                type='breaker',
                                zone_high=ob.zone_high,
                                zone_low=ob.zone_low,
                                time=df.index[i],
                                index=i,
                                strength=ob.strength * 1.5,  # Breakers are stronger
                                broken=True
                            )
                            breakers.append(breaker)
                            ob.broken = True
                            break

                elif ob.type == 'bearish' and not ob.broken:
                    # Check if price broke above this OB
                    ob_index = ob.index
                    for i in range(ob_index + 1, len(df)):
                        if df['close'].iloc[i] > ob.zone_high:
                            breaker = OrderBlock(
                                type='breaker',
                                zone_high=ob.zone_high,
                                zone_low=ob.zone_low,
                                time=df.index[i],
                                index=i,
                                strength=ob.strength * 1.5,
                                broken=True
                            )
                            breakers.append(breaker)
                            ob.broken = True
                            break

            return breakers

        except Exception as e:
            logger.error(f"Error detecting breaker blocks: {e}")
            return []

    @staticmethod
    def is_silver_bullet_time(current_time: datetime) -> Tuple[bool, str]:
        """
        Detect Silver Bullet timing windows (ICT Killzones)
        - Asian Killzone: 02:00-05:00 EST
        - London Killzone: 02:00-05:00 EST (London open)
        - NY AM Killzone: 08:30-11:00 EST
        - NY PM Killzone: 13:30-16:00 EST
        """
        try:
            hour = current_time.hour
            minute = current_time.minute

            # Asian Killzone (20:00-23:00 UTC)
            if 20 <= hour < 23:
                return True, "asian_killzone"

            # London Killzone (02:00-05:00 UTC)
            if 2 <= hour < 5:
                return True, "london_killzone"

            # NY AM Killzone (13:30-16:00 UTC)
            if (hour == 13 and minute >= 30) or (14 <= hour < 16):
                return True, "ny_am_killzone"

            # NY PM Killzone (18:30-21:00 UTC)
            if (hour == 18 and minute >= 30) or (19 <= hour < 21):
                return True, "ny_pm_killzone"

            return False, None

        except Exception as e:
            logger.error(f"Error checking silver bullet time: {e}")
            return False, None

    @staticmethod
    def calculate_institutional_order_flow(df: pd.DataFrame) -> Dict:
        """
        Calculate institutional order flow
        Analyzes volume, body-to-wick ratios, and momentum to detect smart money
        """
        try:
            if len(df) < 20:
                return {'flow': 'neutral', 'strength': 0}

            recent_bars = df.tail(20)

            # Calculate metrics
            avg_volume = recent_bars['tick_volume'].mean() if 'tick_volume' in recent_bars else 0
            recent_volume = recent_bars['tick_volume'].iloc[-5:].mean() if 'tick_volume' in recent_bars else 0

            # Body to wick ratio (institutional candles have large bodies)
            bodies = abs(recent_bars['close'] - recent_bars['open'])
            wicks = (recent_bars['high'] - recent_bars['low']) - bodies
            body_wick_ratio = (bodies / wicks).replace([np.inf, -np.inf], 0).mean()

            # Momentum
            close_change = recent_bars['close'].iloc[-1] - recent_bars['close'].iloc[0]
            momentum = close_change / recent_bars['close'].iloc[0]

            # Volume surge indicates institutional activity
            volume_surge = recent_volume / avg_volume if avg_volume > 0 else 1

            # Determine flow direction
            if momentum > 0.005 and volume_surge > 1.5 and body_wick_ratio > 0.6:
                flow = 'bullish_institutional'
                strength = min(momentum * volume_surge * body_wick_ratio, 10)
            elif momentum < -0.005 and volume_surge > 1.5 and body_wick_ratio > 0.6:
                flow = 'bearish_institutional'
                strength = min(abs(momentum) * volume_surge * body_wick_ratio, 10)
            else:
                flow = 'neutral'
                strength = 0

            return {
                'flow': flow,
                'strength': strength,
                'volume_surge': volume_surge,
                'body_wick_ratio': body_wick_ratio,
                'momentum': momentum
            }

        except Exception as e:
            logger.error(f"Error calculating institutional order flow: {e}")
            return {'flow': 'neutral', 'strength': 0}

    @staticmethod
    def calculate_volume_profile(df: pd.DataFrame, bins: int = 20) -> Dict:
        """
        Calculate Volume Profile
        POC = Point of Control (highest volume price)
        VAH = Value Area High (70% volume upper bound)
        VAL = Value Area Low (70% volume lower bound)
        """
        try:
            if len(df) < 20 or 'tick_volume' not in df.columns:
                return {'poc': 0, 'vah': 0, 'val': 0}

            # Get price range
            high = df['high'].max()
            low = df['low'].min()
            range_size = high - low

            if range_size == 0:
                return {'poc': df['close'].iloc[-1], 'vah': high, 'val': low}

            # Create price bins
            bin_size = range_size / bins
            volume_at_price = np.zeros(bins)

            # Distribute volume to price bins
            for i in range(len(df)):
                bar_high = df['high'].iloc[i]
                bar_low = df['low'].iloc[i]
                bar_volume = df['tick_volume'].iloc[i] if 'tick_volume' in df else 1

                # Find which bins this bar touches
                low_bin = int((bar_low - low) / bin_size)
                high_bin = int((bar_high - low) / bin_size)

                low_bin = max(0, min(bins - 1, low_bin))
                high_bin = max(0, min(bins - 1, high_bin))

                # Distribute volume across touched bins
                for b in range(low_bin, high_bin + 1):
                    volume_at_price[b] += bar_volume / (high_bin - low_bin + 1)

            # Find POC (highest volume)
            poc_bin = np.argmax(volume_at_price)
            poc_price = low + (poc_bin + 0.5) * bin_size

            # Calculate Value Area (70% of volume)
            total_volume = volume_at_price.sum()
            target_volume = total_volume * 0.70

            # Start from POC and expand until we reach 70% volume
            accumulated_volume = volume_at_price[poc_bin]
            val_bin = poc_bin
            vah_bin = poc_bin

            while accumulated_volume < target_volume:
                # Check which direction has more volume
                can_go_lower = val_bin > 0
                can_go_higher = vah_bin < bins - 1

                if not can_go_lower and not can_go_higher:
                    break

                if can_go_lower and not can_go_higher:
                    val_bin -= 1
                    accumulated_volume += volume_at_price[val_bin]
                elif can_go_higher and not can_go_lower:
                    vah_bin += 1
                    accumulated_volume += volume_at_price[vah_bin]
                else:
                    # Both directions available, choose higher volume
                    if volume_at_price[val_bin - 1] > volume_at_price[vah_bin + 1]:
                        val_bin -= 1
                        accumulated_volume += volume_at_price[val_bin]
                    else:
                        vah_bin += 1
                        accumulated_volume += volume_at_price[vah_bin]

            vah_price = low + (vah_bin + 0.5) * bin_size
            val_price = low + (val_bin + 0.5) * bin_size

            return {
                'poc': poc_price,
                'vah': vah_price,
                'val': val_price,
                'volume_distribution': volume_at_price.tolist()
            }

        except Exception as e:
            logger.error(f"Error calculating volume profile: {e}")
            return {'poc': 0, 'vah': 0, 'val': 0}

    @staticmethod
    def detect_inducement(df: pd.DataFrame, lookback: int = 50) -> List[Dict]:
        """
        Detect inducement zones (fake breakouts to trap traders)
        Smart money creates fake moves to trigger stops before real move
        """
        try:
            inducements = []

            if len(df) < lookback:
                return inducements

            for i in range(lookback, len(df) - 5):
                # Look for false breakout high
                local_high = df['high'].iloc[i-lookback:i].max()

                if df['high'].iloc[i] > local_high:
                    # Check if price quickly reversed
                    next_5_closes = df['close'].iloc[i+1:i+6]
                    if len(next_5_closes) > 0 and next_5_closes.min() < df['open'].iloc[i]:
                        inducements.append({
                            'type': 'bullish_trap',
                            'level': df['high'].iloc[i],
                            'time': df.index[i],
                            'reversal_strength': (df['high'].iloc[i] - next_5_closes.min()) / df['high'].iloc[i]
                        })

                # Look for false breakout low
                local_low = df['low'].iloc[i-lookback:i].min()

                if df['low'].iloc[i] < local_low:
                    next_5_closes = df['close'].iloc[i+1:i+6]
                    if len(next_5_closes) > 0 and next_5_closes.max() > df['open'].iloc[i]:
                        inducements.append({
                            'type': 'bearish_trap',
                            'level': df['low'].iloc[i],
                            'time': df.index[i],
                            'reversal_strength': (next_5_closes.max() - df['low'].iloc[i]) / df['low'].iloc[i]
                        })

            return inducements[-5:]  # Return last 5

        except Exception as e:
            logger.error(f"Error detecting inducement: {e}")
            return []

    @staticmethod
    def calculate_power_of_three(df: pd.DataFrame) -> Dict:
        """
        Power of Three: Accumulation -> Manipulation -> Distribution
        Identifies the three phases of institutional price action
        """
        try:
            if len(df) < 30:
                return {'phase': 'unknown', 'confidence': 0}

            recent = df.tail(30)

            # Calculate range and volatility
            price_range = recent['high'].max() - recent['low'].min()
            avg_range = (recent['high'] - recent['low']).mean()

            # Low volatility + ranging = Accumulation
            if price_range < avg_range * 1.5:
                phase = 'accumulation'
                confidence = 0.7

            # High volatility + wicks = Manipulation
            elif price_range > avg_range * 3:
                bodies = abs(recent['close'] - recent['open'])
                wicks = (recent['high'] - recent['low']) - bodies
                if (wicks / bodies).mean() > 1.5:
                    phase = 'manipulation'
                    confidence = 0.8
                else:
                    phase = 'distribution'
                    confidence = 0.6

            # Strong directional move = Distribution
            else:
                price_change = abs(recent['close'].iloc[-1] - recent['close'].iloc[0])
                if price_change > avg_range * 2:
                    phase = 'distribution'
                    confidence = 0.75
                else:
                    phase = 'accumulation'
                    confidence = 0.5

            return {
                'phase': phase,
                'confidence': confidence,
                'range': price_range,
                'avg_range': avg_range
            }

        except Exception as e:
            logger.error(f"Error calculating power of three: {e}")
            return {'phase': 'unknown', 'confidence': 0}
