"""
Backtest Data Manager
Fetches and manages historical market data from MT5 for backtesting
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import logging
from pathlib import Path
import pickle

logger = logging.getLogger(__name__)


class BacktestDataManager:
    """
    Manages historical data for backtesting
    Fetches data from MT5 and caches it for faster subsequent runs
    """

    def __init__(self, symbol: str, cache_dir: str = './backtest_cache'):
        self.symbol = symbol
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.data_cache = {}

    def fetch_historical_data(self, timeframe: str, start_date: datetime,
                             end_date: datetime, use_cache: bool = True) -> Optional[pd.DataFrame]:
        """
        Fetch historical data from MT5 or cache

        Args:
            timeframe: MT5 timeframe (M1, M5, M15, M30, H1, H4, D1)
            start_date: Start date for data
            end_date: End date for data
            use_cache: Whether to use cached data

        Returns:
            DataFrame with OHLCV data
        """
        try:
            # Generate cache key
            cache_key = f"{self.symbol}_{timeframe}_{start_date.date()}_{end_date.date()}"
            cache_file = self.cache_dir / f"{cache_key}.pkl"

            # Check cache first
            if use_cache and cache_file.exists():
                logger.info(f"Loading cached data: {cache_key}")
                with open(cache_file, 'rb') as f:
                    df = pickle.load(f)
                return df

            # Fetch from MT5
            logger.info(f"Fetching historical data from MT5: {self.symbol} {timeframe} "
                       f"{start_date.date()} to {end_date.date()}")

            # Convert timeframe
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

            # Fetch data
            rates = mt5.copy_rates_range(
                self.symbol,
                timeframe_mt5,
                start_date,
                end_date
            )

            if rates is None or len(rates) == 0:
                logger.error(f"No data received from MT5 for {self.symbol} {timeframe}")
                return None

            # Convert to DataFrame
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

            logger.info(f"Fetched {len(df)} bars from {df.index[0]} to {df.index[-1]}")

            # Cache the data
            if use_cache:
                with open(cache_file, 'wb') as f:
                    pickle.dump(df, f)
                logger.info(f"Cached data: {cache_key}")

            return df

        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
            return None

    def fetch_multi_timeframe_data(self, timeframes: Dict[str, str],
                                  start_date: datetime, end_date: datetime,
                                  use_cache: bool = True) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for multiple timeframes

        Args:
            timeframes: Dict of {name: timeframe}, e.g., {'high': 'H4', 'med': 'H1', 'low': 'M15'}
            start_date: Start date
            end_date: End date
            use_cache: Whether to use cache

        Returns:
            Dict of {name: DataFrame}
        """
        data = {}

        for name, tf in timeframes.items():
            df = self.fetch_historical_data(tf, start_date, end_date, use_cache)
            if df is not None:
                data[name] = df
            else:
                logger.error(f"Failed to fetch data for {name} ({tf})")
                return None

        return data

    def get_tick_data(self, bar_time: datetime, timeframe_data: pd.DataFrame) -> Dict:
        """
        Simulate tick data from bar data

        Args:
            bar_time: Current bar time
            timeframe_data: DataFrame with OHLCV data

        Returns:
            Dict with tick data (bid, ask, spread, etc.)
        """
        try:
            if bar_time not in timeframe_data.index:
                return None

            bar = timeframe_data.loc[bar_time]

            # Simulate bid/ask from close price
            # Calculate dynamic spread based on volatility
            spread_pct = 0.0002  # Base 0.02% spread

            # Adjust spread based on bar volatility
            bar_range = bar['high'] - bar['low']
            if bar['close'] > 0:
                volatility_factor = bar_range / bar['close']
                spread_pct = spread_pct * (1 + volatility_factor * 10)  # Scale with volatility

            spread = bar['close'] * spread_pct

            tick = {
                'time': bar_time,
                'bid': bar['close'] - (spread / 2),
                'ask': bar['close'] + (spread / 2),
                'last': bar['close'],
                'volume': bar['tick_volume'],
                'spread': spread,
                'time_msc': int(bar_time.timestamp() * 1000),
                # CRITICAL FIX: Add OHLC data for proper SL/TP checking
                'open': bar['open'],
                'high': bar['high'],
                'low': bar['low'],
                'close': bar['close'],
            }

            return tick

        except Exception as e:
            logger.error(f"Error getting tick data: {e}")
            return None

    def clear_cache(self):
        """Clear all cached data"""
        try:
            for file in self.cache_dir.glob("*.pkl"):
                file.unlink()
            logger.info("Cache cleared")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
