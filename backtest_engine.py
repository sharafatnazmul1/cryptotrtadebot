"""
Backtest Engine
Runs the complete trading bot in backtest mode with historical data
"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import logging
from pathlib import Path
import MetaTrader5 as mt5

from backtest_data import BacktestDataManager
from backtest_broker import BacktestBroker
from indicators import Indicators
from indicators_advanced import AdvancedSMCIndicators
from signal_engine import SignalEngine
from risk import RiskManager
from risk_advanced import AdvancedRiskManager
from position_manager_advanced import AdvancedPositionManager
from ml_signal_filter import MLSignalFilter
from small_capital_optimizer import SmallCapitalOptimizer
from order_manager import OrderManager
from persistence import Persistence

logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    Complete backtesting engine that simulates the entire trading bot
    """

    def __init__(self, config: Dict, start_date: datetime, end_date: datetime,
                 initial_balance: float = 1000):
        """
        Initialize backtest engine

        Args:
            config: Trading configuration
            start_date: Backtest start date
            end_date: Backtest end date
            initial_balance: Starting balance
        """
        self.config = config
        self.start_date = start_date
        self.end_date = end_date
        self.initial_balance = initial_balance

        # Data manager
        self.data_manager = BacktestDataManager(config['symbol'])

        # Symbol info (get from MT5)
        self.symbol_info = self._get_symbol_info()

        # Simulated broker
        self.broker = BacktestBroker(config, initial_balance, self.symbol_info)

        # Create mock MT5 client that uses broker
        self.mt5_client = self._create_mock_mt5_client()

        # Initialize persistence (for backtest)
        self.persistence = Persistence(config)

        # Initialize all trading modules
        self._initialize_modules()

        # Backtest state
        self.current_time = None
        self.current_bar = 0
        self.total_bars = 0

        # Performance tracking
        self.equity_curve = []
        self.signals_generated = []
        self.trades_log = []

        logger.info(f"Backtest engine initialized: {start_date.date()} to {end_date.date()}, "
                   f"Balance=${initial_balance:.2f}")

    def _get_symbol_info(self) -> Dict:
        """Get symbol information from MT5 or use defaults"""
        try:
            # Try to get from config first
            if 'symbol_specs' in self.config:
                logger.info("Using symbol specs from config")
                return self.config['symbol_specs']

            # Try to get from MT5 if available
            try:
                if mt5.initialize():
                    logger.info("Fetching symbol info from MT5")
                    info = mt5.symbol_info(self.config['symbol'])
                    mt5.shutdown()

                    if info is not None:
                        logger.info(f"Got symbol info from MT5 for {self.config['symbol']}")
                        return {
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
            except Exception as e:
                logger.warning(f"Could not get symbol info from MT5: {e}")

            # Fall back to defaults
            logger.info("Using default symbol specifications")
            return self._get_default_symbol_info()

        except Exception as e:
            logger.error(f"Error getting symbol info: {e}")
            return self._get_default_symbol_info()

    def _get_default_symbol_info(self) -> Dict:
        """Get default symbol info for crypto"""
        return {
            'point': 0.01,
            'digits': 2,
            'contract_size': 1.0,
            'min_lot': 0.01,
            'max_lot': 100.0,
            'lot_step': 0.01,
            'tick_size': 0.01,
            'tick_value': 1.0,
            'spread': 20,
            'stops_level': 0,
            'freeze_level': 0,
        }

    def _create_mock_mt5_client(self):
        """Create mock MT5 client that uses backtest broker"""
        class MockMT5Client:
            def __init__(self, broker, symbol_info, data_manager, config):
                self.broker = broker
                self.symbol_info = symbol_info
                self.data_manager = data_manager
                self.config = config
                self.connected = True
                self.symbol = config['symbol']
                self.current_tick = None

            def get_account_info(self):
                return self.broker.get_account_info()

            def get_positions(self, symbol=None):
                return self.broker.get_positions(symbol)

            def get_orders(self, symbol=None):
                return self.broker.get_orders(symbol)

            def place_order(self, order_request):
                return self.broker.place_order(order_request, self.current_tick, self.data_manager.current_time)

            def close_position(self, ticket):
                return self.broker.close_position(ticket, self.current_tick, self.data_manager.current_time)

            def cancel_order(self, ticket):
                return self.broker.cancel_order(ticket)

            def modify_order(self, ticket, sl=None, tp=None):
                return self.broker.modify_position(ticket, sl, tp)

            def get_tick(self):
                return self.current_tick

            def get_bars(self, timeframe, count):
                # This will be set by backtest engine
                return None

        return MockMT5Client(self.broker, self.symbol_info, self.data_manager, self.config)

    def _initialize_modules(self):
        """Initialize all trading modules"""
        try:
            # Signal engine
            self.signal_engine = SignalEngine(self.config, self.mt5_client)

            # Risk managers
            self.risk_manager = RiskManager(self.config, self.mt5_client, self.persistence)
            self.advanced_risk = AdvancedRiskManager(self.config)

            # Position manager
            self.position_manager = AdvancedPositionManager(self.config)

            # ML filter
            self.ml_filter = MLSignalFilter(self.config)

            # Small capital optimizer
            self.small_capital_optimizer = SmallCapitalOptimizer(self.config)

            # Order manager
            self.order_manager = OrderManager(self.config, self.mt5_client,
                                             self.risk_manager, self.persistence)

            logger.info("All trading modules initialized")

        except Exception as e:
            logger.error(f"Error initializing modules: {e}")
            raise

    def run(self, use_cache: bool = True, progress_callback: Optional[callable] = None) -> Dict:
        """
        Run the backtest

        Args:
            use_cache: Whether to use cached data
            progress_callback: Optional callback for progress updates

        Returns:
            Dict with backtest results
        """
        try:
            logger.info("="*80)
            logger.info(f"STARTING BACKTEST: {self.config['symbol']} from {self.start_date.date()} to {self.end_date.date()}")
            logger.info("="*80)

            # Fetch historical data
            timeframes = {
                'high': self.config['timeframes']['high'],
                'med': self.config['timeframes']['med'],
                'low': self.config['timeframes']['low'],
            }

            data = self.data_manager.fetch_multi_timeframe_data(
                timeframes, self.start_date, self.end_date, use_cache
            )

            if not data or 'med' not in data:
                logger.error("Failed to fetch historical data")
                return None

            # Use medium timeframe as main timeframe for iteration
            main_data = data['med']
            self.total_bars = len(main_data)

            logger.info(f"Loaded {self.total_bars} bars for backtesting")

            # Run through each bar
            for i, (bar_time, bar) in enumerate(main_data.iterrows()):
                self.current_bar = i
                self.current_time = bar_time
                self.data_manager.current_time = bar_time

                # Update progress
                if progress_callback and i % 100 == 0:
                    progress = (i / self.total_bars) * 100
                    progress_callback(progress, bar_time)

                # Update current tick
                self.mt5_client.current_tick = self.data_manager.get_tick_data(bar_time, main_data)

                if not self.mt5_client.current_tick:
                    continue

                # Update broker (check SL/TP hits, pending orders)
                self.broker.check_pending_orders(self.mt5_client.current_tick, bar_time)
                self.broker.update_positions(self.mt5_client.current_tick, bar_time)

                # Record equity
                account_info = self.broker.get_account_info()
                self.equity_curve.append({
                    'time': bar_time,
                    'balance': account_info['balance'],
                    'equity': account_info['equity'],
                    'profit': account_info['profit'],
                })

                # Provide historical data to mt5_client for indicators
                self._provide_historical_data(data, bar_time)

                # Update position management
                self._update_positions()

                # Check if we should generate signals (not on every bar)
                if i % self.config.get('signal_check_interval', 5) == 0:
                    self._process_trading_logic()

            # Finalize backtest
            results = self._generate_results()

            logger.info("="*80)
            logger.info("BACKTEST COMPLETED")
            logger.info("="*80)

            return results

        except Exception as e:
            logger.error(f"Error running backtest: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _provide_historical_data(self, data: Dict, current_time: datetime):
        """Provide historical data up to current time for indicators"""
        try:
            # For each timeframe, provide data up to current bar
            self.mt5_client.htf_data = data['high'][data['high'].index <= current_time].tail(100)
            self.mt5_client.mtf_data = data['med'][data['med'].index <= current_time].tail(100)
            self.mt5_client.ltf_data = data['low'][data['low'].index <= current_time].tail(50) if 'low' in data else None

            # Mock get_bars method
            def get_bars_mock(timeframe, count):
                if timeframe == self.config['timeframes']['high']:
                    return self.mt5_client.htf_data.tail(count)
                elif timeframe == self.config['timeframes']['med']:
                    return self.mt5_client.mtf_data.tail(count)
                elif timeframe == self.config['timeframes']['low']:
                    return self.mt5_client.ltf_data.tail(count) if self.mt5_client.ltf_data is not None else None
                return None

            self.mt5_client.get_bars = get_bars_mock

        except Exception as e:
            logger.error(f"Error providing historical data: {e}")

    def _update_positions(self):
        """Update position management"""
        try:
            positions = self.broker.get_positions(self.config['symbol'])

            for pos in positions:
                # Check if we're tracking this position
                if pos['ticket'] not in self.position_manager.positions:
                    # Add to position manager
                    self.position_manager.add_position(
                        pos['ticket'],
                        pos['symbol'],
                        pos['type'],
                        pos['price'],
                        pos['volume'],
                        pos['sl'],
                        pos['tp'],
                        pos['time']
                    )

                # Update position
                action = self.position_manager.update_position(
                    pos['ticket'],
                    self.mt5_client.current_tick['bid'] if pos['type'] == 'BUY' else self.mt5_client.current_tick['ask'],
                    self.mt5_client
                )

                # Execute action if returned
                if action:
                    if action['action'] == 'modify_sl':
                        self.broker.modify_position(action['ticket'], sl=action['new_sl'])
                    elif action['action'] == 'partial_close':
                        # For simplicity, close entire position in backtest
                        # (partial closes would require volume tracking)
                        pass

        except Exception as e:
            logger.error(f"Error updating positions: {e}")

    def _process_trading_logic(self):
        """Process trading logic (signal generation and execution)"""
        try:
            # Generate signal
            signal = self.signal_engine.analyze()

            if signal:
                self.signals_generated.append({
                    'time': self.current_time,
                    'signal': signal
                })

                logger.info(f"Signal generated: {signal['side']} @ {signal['entry_price']:.5f}, "
                           f"score={signal['signal_score']}, RR={signal['rr_ratio']:.2f}")

                # Filter with ML
                if self.ml_filter:
                    quality = self.ml_filter.predict_signal_quality(signal, self.mt5_client.mtf_data)
                    signal['ml_confidence'] = quality.score

                    if quality.prediction == 'skip':
                        logger.info(f"Signal filtered by ML: confidence={quality.score:.2f}")
                        return

                # Check small capital criteria
                account = self.broker.get_account_info()
                can_trade, reason = self.small_capital_optimizer.should_take_signal(
                    signal, account['balance']
                )

                if not can_trade:
                    logger.info(f"Signal rejected: {reason}")
                    return

                # Process signal through order manager
                success, result = self.order_manager.process_signal(signal)

                if success:
                    logger.info(f"Order placed: ticket={result.get('order')}")
                    self.trades_log.append({
                        'time': self.current_time,
                        'signal': signal,
                        'result': result
                    })
                else:
                    logger.warning(f"Order failed: {result.get('error')}")

        except Exception as e:
            logger.error(f"Error processing trading logic: {e}")

    def _generate_results(self) -> Dict:
        """Generate comprehensive backtest results"""
        try:
            # Get broker statistics
            stats = self.broker.get_statistics()

            # Calculate equity curve metrics
            equity_df = pd.DataFrame(self.equity_curve)

            if len(equity_df) > 0:
                equity_df.set_index('time', inplace=True)

                # Drawdown analysis
                equity_df['peak'] = equity_df['equity'].cummax()
                equity_df['drawdown'] = equity_df['equity'] - equity_df['peak']
                equity_df['drawdown_pct'] = (equity_df['drawdown'] / equity_df['peak']) * 100

                max_drawdown = equity_df['drawdown_pct'].min()
                max_drawdown_duration = self._calculate_max_drawdown_duration(equity_df)

                # Sharpe ratio (simplified)
                returns = equity_df['equity'].pct_change().dropna()
                sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252) if len(returns) > 1 and returns.std() > 0 else 0

            else:
                max_drawdown = 0
                max_drawdown_duration = 0
                sharpe_ratio = 0

            # Compile results
            results = {
                'summary': {
                    'start_date': self.start_date,
                    'end_date': self.end_date,
                    'duration_days': (self.end_date - self.start_date).days,
                    'initial_balance': self.initial_balance,
                    'final_balance': stats.get('current_balance', 0),
                    'final_equity': stats.get('current_equity', 0),
                    'net_profit': stats.get('net_profit', 0),
                    'return_pct': stats.get('return_pct', 0),
                    'max_drawdown_pct': max_drawdown,
                    'max_drawdown_duration_days': max_drawdown_duration,
                    'sharpe_ratio': sharpe_ratio,
                },
                'trades': {
                    'total': stats.get('total_trades', 0),
                    'wins': stats.get('winning_trades', 0),
                    'losses': stats.get('losing_trades', 0),
                    'win_rate_pct': stats.get('win_rate', 0),
                    'avg_win': stats.get('avg_win', 0),
                    'avg_loss': stats.get('avg_loss', 0),
                    'largest_win': stats.get('largest_win', 0),
                    'largest_loss': stats.get('largest_loss', 0),
                    'profit_factor': stats.get('profit_factor', 0),
                },
                'signals': {
                    'total_generated': len(self.signals_generated),
                    'total_executed': len(self.trades_log),
                    'execution_rate_pct': (len(self.trades_log) / len(self.signals_generated) * 100) if self.signals_generated else 0,
                },
                'equity_curve': equity_df if len(equity_df) > 0 else None,
                'closed_trades': self.broker.closed_trades,
                'all_signals': self.signals_generated,
            }

            return results

        except Exception as e:
            logger.error(f"Error generating results: {e}")
            return {}

    def _calculate_max_drawdown_duration(self, equity_df: pd.DataFrame) -> float:
        """Calculate maximum drawdown duration in days"""
        try:
            in_drawdown = False
            start_time = None
            max_duration = timedelta(0)

            for idx, row in equity_df.iterrows():
                if row['drawdown'] < 0:
                    if not in_drawdown:
                        in_drawdown = True
                        start_time = idx
                else:
                    if in_drawdown:
                        duration = idx - start_time
                        if duration > max_duration:
                            max_duration = duration
                        in_drawdown = False

            return max_duration.days

        except Exception as e:
            logger.error(f"Error calculating drawdown duration: {e}")
            return 0
