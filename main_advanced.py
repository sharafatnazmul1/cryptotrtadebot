"""
Advanced Professional Trading Bot - Main Entry Point
Fully Integrated Hedge Fund-Grade System with ALL Advanced Features

This version integrates:
- Advanced SMC/ICT indicators (Premium/Discount, OTE, Breaker Blocks, etc.)
- Kelly Criterion and adaptive risk management
- Multi-symbol support with correlation analysis
- Advanced position management (trailing stops, partial profits, break-even)
- Machine learning signal filtering
- Telegram notifications
- Small capital optimization
"""

import sys
import os
import time
import signal
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional
import yaml
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import base modules
from mt5_client import MT5Client
from persistence import Persistence

# Import advanced modules
from indicators_advanced import AdvancedSMCIndicators
from risk_advanced import AdvancedRiskManager
from position_manager_advanced import AdvancedPositionManager
from ml_signal_filter import MLSignalFilter
from small_capital_optimizer import SmallCapitalOptimizer
from telegram_notifier import TelegramNotifier, NotificationConfig

# Import basic modules (we'll enhance them)
from indicators import Indicators
from signal_engine import SignalEngine
from order_manager import OrderManager

logger = logging.getLogger(__name__)


class SafeConsoleFormatter(logging.Formatter):
    """
    Custom formatter that removes emojis on Windows to prevent UnicodeEncodeError.
    Preserves emojis on Linux/Mac and in file logs.
    """
    def __init__(self, fmt=None, datefmt=None, remove_emojis=False):
        super().__init__(fmt, datefmt)
        self.remove_emojis = remove_emojis

    def format(self, record):
        # Format the message normally
        formatted = super().format(record)

        # On Windows console, replace emojis with safe alternatives
        if self.remove_emojis:
            # Replace common emojis with ASCII alternatives
            emoji_map = {
                '🚀': '[START]',
                '✓': '[OK]',
                '✅': '[SUCCESS]',
                '❌': '[FAIL]',
                '⚠️': '[WARN]',
                '📊': '[STATS]',
                '💰': '$',
                '📈': '[UP]',
                '📉': '[DOWN]',
                '🔔': '[ALERT]',
                '⏰': '[TIME]',
                '🎯': '[TARGET]',
                '🔥': '[HOT]',
                '💡': '[INFO]',
                '🛑': '[STOP]',
            }

            for emoji, replacement in emoji_map.items():
                formatted = formatted.replace(emoji, replacement)

            # Remove any remaining emojis (Unicode range for emojis)
            import re
            # Remove emoji characters
            emoji_pattern = re.compile(
                "["
                "\U0001F600-\U0001F64F"  # emoticons
                "\U0001F300-\U0001F5FF"  # symbols & pictographs
                "\U0001F680-\U0001F6FF"  # transport & map symbols
                "\U0001F1E0-\U0001F1FF"  # flags (iOS)
                "\U00002702-\U000027B0"  # dingbats
                "\U000024C2-\U0001F251"
                "\U0001F900-\U0001F9FF"  # supplemental symbols
                "\U00002500-\U00002BEF"  # chinese characters
                "]+",
                flags=re.UNICODE
            )
            formatted = emoji_pattern.sub('', formatted)

        return formatted


def setup_logging(config: Dict):
    """Setup logging configuration with full Windows compatibility"""
    import sys
    import re

    log_level = getattr(logging, config.get('system', {}).get('log_level', 'INFO'))
    log_dir = Path('./logs')
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / f"trading_bot_{datetime.now().strftime('%Y%m%d')}.log"

    # Detect if we're on Windows with cp1252 console
    is_windows_console = (
        sys.platform == 'win32' and
        hasattr(sys.stdout, 'encoding') and
        'cp' in sys.stdout.encoding.lower()
    )

    # File handler with UTF-8 encoding (always preserves emojis in log files)
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(log_level)
    file_handler.setFormatter(
        SafeConsoleFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            remove_emojis=False  # Keep emojis in file
        )
    )

    # Console handler with safe formatting for Windows
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(
        SafeConsoleFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            remove_emojis=is_windows_console  # Remove emojis only on Windows console
        )
    )

    # Setup root logger
    logging.basicConfig(
        level=log_level,
        handlers=[file_handler, console_handler],
        force=True  # Force reconfiguration
    )

    # Suppress noisy loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)

    return logging.getLogger(__name__)


class AdvancedTradingBot:
    """
    Professional Trading Bot with Full Integration of Advanced Features
    """

    def __init__(self, config_file: str):
        """Initialize bot with configuration"""
        self.config = self._load_config(config_file)
        self.logger = setup_logging(self.config)

        self.logger.info("=" * 80)
        self.logger.info("🚀 ADVANCED PROFESSIONAL TRADING BOT STARTING")
        self.logger.info("=" * 80)
        self.logger.info(f"Config: {config_file}")

        # Initialize components
        self.mt5_client = None
        self.persistence = None
        self.small_cap_optimizer = None
        self.risk_manager = None
        self.position_manager = None
        self.signal_engine = None
        self.order_manager = None
        self.ml_filter = None
        self.telegram = None

        # Advanced indicators
        self.advanced_indicators = AdvancedSMCIndicators()
        self.basic_indicators = Indicators()

        # Control flags
        self.running = False
        self.shutdown_requested = False

        # Statistics
        self.stats = {
            'start_time': datetime.now(timezone.utc),
            'signals_generated': 0,
            'signals_filtered': 0,
            'orders_placed': 0,
            'positions_modified': 0,
            'errors': 0,
        }

    def _load_config(self, config_file: str) -> Dict:
        """Load configuration from YAML file"""
        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)

            # Override with environment variables
            if os.getenv('MT5_LOGIN'):
                if 'mt5' not in config:
                    config['mt5'] = {}
                config['mt5']['login'] = int(os.getenv('MT5_LOGIN'))
            if os.getenv('MT5_PASSWORD'):
                config['mt5']['password'] = os.getenv('MT5_PASSWORD')
            if os.getenv('MT5_SERVER'):
                config['mt5']['server'] = os.getenv('MT5_SERVER')
            if os.getenv('MT5_PATH'):
                config['mt5']['path'] = os.getenv('MT5_PATH')
            if os.getenv('TRADING_MODE'):
                config['mode'] = os.getenv('TRADING_MODE')

            return config

        except Exception as e:
            print(f"Error loading config: {e}")
            sys.exit(1)

    def initialize(self) -> bool:
        """Initialize all components"""
        try:
            self.logger.info("Initializing components...")

            # Initialize persistence
            self.logger.info("✓ Initializing persistence...")
            self.persistence = Persistence(self.config)

            # Initialize MT5 client
            self.logger.info("✓ Initializing MT5 client...")
            self.mt5_client = MT5Client(self.config)
            if not self.mt5_client.initialize():
                self.logger.error("Failed to initialize MT5 client")
                return False

            # Get account info for optimization
            account = self.mt5_client.get_account_info()
            balance = account.get('balance', 0) if account else 0

            # Initialize small capital optimizer
            self.logger.info("✓ Initializing small capital optimizer...")
            self.small_cap_optimizer = SmallCapitalOptimizer(self.config)

            # Determine account tier and optimize settings
            tier = self.small_cap_optimizer.get_account_tier(balance)
            self.logger.info(f"  Account tier: {tier} (${balance:.2f})")

            # Get optimized parameters
            optimized_risk = self.small_cap_optimizer.get_optimized_risk(balance)
            loss_limits = self.small_cap_optimizer.get_loss_limits(balance)
            pos_mgmt_params = self.small_cap_optimizer.get_position_management_params(balance)

            self.logger.info(f"  Optimized risk: {optimized_risk}%")
            self.logger.info(f"  Daily loss limit: {loss_limits['daily']}%")

            # Override config with optimized values
            self.config['risk_pct_per_trade'] = optimized_risk
            self.config['max_daily_loss_pct'] = loss_limits['daily']
            self.config['max_weekly_loss_pct'] = loss_limits.get('weekly', 5.0)
            self.config['max_monthly_loss_pct'] = loss_limits.get('monthly', 10.0)

            # Initialize advanced risk manager
            self.logger.info("✓ Initializing advanced risk manager...")
            self.risk_manager = AdvancedRiskManager(self.config)
            self.risk_manager.peak_balance = balance

            # Initialize advanced position manager
            self.logger.info("✓ Initializing advanced position manager...")
            position_config = self.config.copy()
            position_config.update({
                'enable_trailing_stop': True,
                'trailing_activation_pct': pos_mgmt_params.get('trailing_activation', 1.0),
                'trailing_distance_pct': pos_mgmt_params.get('trailing_distance', 0.5),
                'enable_break_even': True,
                'break_even_activation_pct': pos_mgmt_params.get('break_even_activation', 0.5),
                'break_even_buffer_pct': pos_mgmt_params.get('break_even_buffer', 0.1),
                'enable_partial_profit': True,
                'partial_profit_levels': pos_mgmt_params.get('partial_profits', []),
                'max_position_hold_hours': pos_mgmt_params.get('max_hold_hours', 24),
            })
            self.position_manager = AdvancedPositionManager(position_config)

            # Initialize ML signal filter
            self.logger.info("✓ Initializing ML signal filter...")
            ml_config = self.config.get('machine_learning', {})
            ml_config['model_path'] = './models'
            self.ml_filter = MLSignalFilter(ml_config)

            # Initialize Telegram notifier
            self.logger.info("✓ Initializing Telegram notifier...")
            telegram_config = self.config.get('telegram', {})
            notif_config = NotificationConfig(
                bot_token=os.getenv('TELEGRAM_BOT_TOKEN', ''),
                chat_id=os.getenv('TELEGRAM_CHAT_ID', ''),
                enabled=telegram_config.get('enabled', False),
                notify_signals=telegram_config.get('notify_signals', True),
                notify_trades=telegram_config.get('notify_trades', True),
                notify_errors=telegram_config.get('notify_errors', True),
                notify_daily_summary=telegram_config.get('notify_daily_summary', True)
            )
            self.telegram = TelegramNotifier(notif_config)

            # Initialize signal engine (we'll enhance it with advanced indicators)
            self.logger.info("✓ Initializing enhanced signal engine...")
            self.signal_engine = SignalEngine(self.config, self.mt5_client)

            # Initialize order manager
            self.logger.info("✓ Initializing order manager...")
            self.order_manager = OrderManager(
                self.config,
                self.mt5_client,
                self.risk_manager,
                self.persistence
            )

            self.logger.info("=" * 80)
            self.logger.info("✅ ALL COMPONENTS INITIALIZED SUCCESSFULLY")
            self.logger.info("=" * 80)

            # Send startup notification
            if self.telegram.config.enabled:
                self.telegram.notify_bot_started_sync(
                    "Advanced Trading Bot",
                    {
                        'symbols': [self.config.get('symbol', 'BTCUSD')],
                        'risk_pct': optimized_risk,
                        'max_daily_loss': loss_limits['daily'],
                        'max_positions': self.config.get('max_concurrent_trades', 3),
                        'account_tier': tier,
                        'balance': balance
                    }
                )

            return True

        except Exception as e:
            self.logger.error(f"Initialization error: {e}", exc_info=True)
            return False

    def run(self):
        """Main bot loop"""
        if not self.initialize():
            self.logger.error("Failed to initialize bot")
            return

        self.running = True
        self.logger.info("🚀 Bot started - entering main loop")

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Main loop
        tick_count = 0
        analysis_interval = self.config.get('system', {}).get('loop_interval_seconds', 1)
        maintenance_interval = self.config.get('system', {}).get('maintenance_interval_seconds', 300)
        position_check_interval = 10  # Check positions every 10 seconds

        last_analysis = time.time()
        last_maintenance = time.time()
        last_position_check = time.time()

        while self.running and not self.shutdown_requested:
            try:
                current_time = time.time()

                # Check and update positions
                if current_time - last_position_check >= position_check_interval:
                    self._check_positions()
                    last_position_check = current_time

                # Perform market analysis
                if current_time - last_analysis >= analysis_interval:
                    self._perform_analysis()
                    last_analysis = current_time
                    tick_count += 1

                # Perform maintenance
                if current_time - last_maintenance >= maintenance_interval:
                    self._perform_maintenance()
                    last_maintenance = current_time

                # Brief sleep
                time.sleep(0.1)

            except KeyboardInterrupt:
                self.logger.info("Keyboard interrupt received")
                break

            except Exception as e:
                self.logger.error(f"Error in main loop: {e}", exc_info=True)
                self.stats['errors'] += 1

                if self.stats['errors'] > 10:
                    self.logger.error("Too many errors, entering safe mode")
                    self._enter_safe_mode()
                    break

                time.sleep(1)

        self.shutdown()

    def _perform_analysis(self):
        """Perform market analysis with advanced features"""
        try:
            mode = self.config.get('mode', 'demo')

            # Generate base signal
            signal = self.signal_engine.analyze()

            if signal:
                self.stats['signals_generated'] += 1
                self.logger.info(f"📊 Signal generated: {signal['side']} at {signal['entry_price']:.5f}")

                # Get market data for advanced analysis
                symbol = self.config.get('symbol', 'BTCUSD')
                df = self.mt5_client.get_bars('M5', 100)

                if df is not None and len(df) > 0:
                    # Add advanced indicator analysis
                    signal = self._enhance_signal_with_advanced_indicators(signal, df)

                    # Get account info
                    account = self.mt5_client.get_account_info()
                    balance = account.get('balance', 0) if account else 0

                    # Check with small capital optimizer
                    daily_trades = self.stats.get('trades_today', 0)
                    should_take, reason = self.small_cap_optimizer.should_take_signal(
                        signal, balance, daily_trades
                    )

                    if not should_take:
                        self.logger.info(f"❌ Signal rejected by optimizer: {reason}")
                        self.stats['signals_filtered'] += 1
                        self.persistence.save_signal(signal, status='FILTERED_OPTIMIZER')
                        return

                    # ML signal filtering
                    if self.config.get('machine_learning', {}).get('enabled', True):
                        ml_quality = self.ml_filter.predict_signal_quality(signal, df)
                        signal['ml_confidence'] = ml_quality.confidence
                        signal['ml_score'] = ml_quality.score

                        min_confidence = self.config.get('machine_learning', {}).get('min_confidence', 0.6)
                        if ml_quality.prediction == 'skip' or ml_quality.confidence < min_confidence:
                            self.logger.info(f"❌ Signal rejected by ML: confidence {ml_quality.confidence:.2%}")
                            self.stats['signals_filtered'] += 1
                            self.persistence.save_signal(signal, status='FILTERED_ML')
                            #return

                    # Signal passed all filters!
                    self.logger.info(f"✅ Signal approved - proceeding to trade")
                    self.persistence.save_signal(signal, status='APPROVED')

                    # Send signal notification
                    if self.telegram.config.enabled and self.telegram.config.notify_signals:
                        self.telegram.notify_signal_generated_sync(signal)

                    # Process signal if not in dry run
                    if mode != 'dry_run':
                        if self.signal_engine.validate_signal(signal):
                            # Check risk limits
                            risk_check = self.risk_manager.check_signal(signal, balance, 0, {})

                            if risk_check.get('allowed', False):
                                # Calculate optimized lot size
                                lot_size = self._calculate_optimized_lot_size(signal, account)
                                signal['lot_size'] = lot_size

                                # Place order
                                success, result = self.order_manager.process_signal(signal)

                                if success:
                                    self.stats['orders_placed'] += 1
                                    self.stats['trades_today'] = self.stats.get('trades_today', 0) + 1
                                    self.logger.info(f"✅ Order placed: {result.get('order')}")

                                    # Add position to tracker
                                    if result.get('filled'):
                                        ticket = result.get('ticket')
                                        self.position_manager.add_position(
                                            ticket=ticket,
                                            symbol=signal['symbol'],
                                            side=signal['side'],
                                            entry_price=signal['entry_price'],
                                            volume=lot_size,
                                            stop_loss=signal['sl_price'],
                                            take_profit=signal['tp_price'],
                                            open_time=datetime.utcnow()
                                        )

                                    # Send trade notification
                                    if self.telegram.config.enabled:
                                        self.telegram.notify_trade_opened_sync({
                                            'symbol': signal['symbol'],
                                            'ticket': result.get('ticket', 0),
                                            'side': signal['side'],
                                            'volume': lot_size,
                                            'entry_price': signal['entry_price'],
                                            'stop_loss': signal['sl_price'],
                                            'take_profit': signal['tp_price'],
                                            'risk_amount': balance * (self.config.get('risk_pct_per_trade', 0.5) / 100),
                                            'risk_pct': self.config.get('risk_pct_per_trade', 0.5)
                                        })
                                else:
                                    self.logger.warning(f"❌ Order placement failed: {result.get('error')}")
                            else:
                                self.logger.warning(f"❌ Risk check failed: {risk_check.get('reason', 'Unknown')}")
                    else:
                        self.logger.info("ℹ️ Dry run mode - order not placed")

            # Manage existing orders
            if mode != 'dry_run':
                self.order_manager.manage_pending_orders()

        except Exception as e:
            self.logger.error(f"Error in analysis: {e}", exc_info=True)
            self.stats['errors'] += 1

    def _enhance_signal_with_advanced_indicators(self, signal: Dict, df) -> Dict:
        """Enhance signal with advanced SMC/ICT indicators"""
        try:
            # Calculate premium/discount zones
            high = df['high'].max()
            low = df['low'].min()
            pd_zone = self.advanced_indicators.calculate_premium_discount(high, low)

            if pd_zone:
                current_price = df['close'].iloc[-1]
                signal['in_premium'] = current_price > pd_zone.equilibrium
                signal['in_discount'] = current_price < pd_zone.equilibrium
                signal['in_ote_buy'] = pd_zone.ote_buy_low <= current_price <= pd_zone.ote_buy_high
                signal['in_ote_sell'] = pd_zone.ote_sell_low <= current_price <= pd_zone.ote_sell_high

            # Detect market structure (BOS/CHoCH)
            market_structure = self.advanced_indicators.detect_bos_choch(df)
            signal['bos'] = market_structure.bos
            signal['choch'] = market_structure.choch
            signal['mss'] = market_structure.mss

            # Check kill zone timing
            is_killzone, killzone_name = self.advanced_indicators.is_silver_bullet_time(datetime.utcnow())
            signal['in_killzone'] = is_killzone
            signal['killzone'] = killzone_name

            # Institutional order flow
            order_flow = self.advanced_indicators.calculate_institutional_order_flow(df)
            signal['order_flow'] = order_flow['flow']
            signal['order_flow_strength'] = order_flow['strength']

            # Volume profile
            vol_profile = self.advanced_indicators.calculate_volume_profile(df)
            signal['volume_poc'] = vol_profile.get('poc', 0)
            signal['volume_vah'] = vol_profile.get('vah', 0)
            signal['volume_val'] = vol_profile.get('val', 0)

            # Power of Three phase
            power_of_3 = self.advanced_indicators.calculate_power_of_three(df)
            signal['market_phase'] = power_of_3['phase']
            signal['phase_confidence'] = power_of_3['confidence']

            return signal

        except Exception as e:
            self.logger.error(f"Error enhancing signal: {e}")
            return signal

    def _calculate_optimized_lot_size(self, signal: Dict, account: Dict) -> float:
        """Calculate lot size using advanced risk management"""
        try:
            balance = account.get('balance', 0)

            # Get trade history for Kelly
            recent_trades = self.risk_manager.trade_history[-20:] if len(self.risk_manager.trade_history) >= 20 else []

            if len(recent_trades) >= 20:
                wins = [t for t in recent_trades if t['is_win']]
                losses = [t for t in recent_trades if not t['is_win']]

                win_rate = len(wins) / len(recent_trades)
                avg_win = abs(sum(t['profit'] for t in wins) / len(wins)) if wins else 0
                avg_loss = abs(sum(t['profit'] for t in losses) / len(losses)) if losses else 0
            else:
                win_rate = None
                avg_win = None
                avg_loss = None

            # Calculate position size with Kelly
            position_risk = self.risk_manager.calculate_position_size(
                symbol=signal['symbol'],
                entry_price=signal['entry_price'],
                stop_loss=signal['sl_price'],
                account_balance=balance,
                current_volatility=1.0,
                win_rate=win_rate,
                avg_win=avg_win,
                avg_loss=avg_loss
            )

            if position_risk:
                return position_risk.position_size

            # Fallback to basic calculation
            return 0.01

        except Exception as e:
            self.logger.error(f"Error calculating lot size: {e}")
            return 0.01

    def _check_positions(self):
        """Check and manage all open positions"""
        try:
            positions = self.mt5_client.get_positions(symbol=self.config.get('symbol'))

            for pos in positions:
                if pos.get('magic') == self.config.get('magic', 0):
                    ticket = pos['ticket']
                    if isinstance(pos, dict):
                        current_price = pos.get('price_current', 0)  # Access dictionary key safely
                    else:
                        current_price = getattr(pos, 'price_current', 0)  # Access attribute

                    # Update position manager
                    action = self.position_manager.update_position(
                        ticket, current_price, self.mt5_client
                    )

                    if action:
                        # Execute the action
                        success = self.position_manager.execute_position_action(
                            action, self.mt5_client
                        )

                        if success:
                            self.stats['positions_modified'] += 1
                            self.logger.info(f"✅ Position {ticket} modified: {action['action']}")

                            # Send notification
                            if self.telegram.config.enabled:
                                # Calculate profit percentage safely
                                position_value = pos.get('volume', 0) * pos.get('price_open', 1)
                                profit_pct = (pos.get('profit', 0) / position_value * 100) if position_value > 0 else 0

                                self.telegram.notify_position_modified_sync({
                                    'ticket': ticket,
                                    'symbol': pos['symbol'],
                                    'type': action['reason'],
                                    'new_sl': action.get('new_sl'),
                                    'closed_volume': action.get('volume'),
                                    'profit': pos.get('profit', 0),
                                    'profit_pct': profit_pct
                                })

        except Exception as e:
            self.logger.error(f"Error checking positions: {e}")

    def _perform_maintenance(self):
        """Perform periodic maintenance"""
        try:
            # Log status
            self._log_status()

            # Update symbol info
            self.mt5_client._update_symbol_info()

            # Backup database
            if time.time() - self.stats.get('last_backup', 0) > 3600:
                self.persistence.backup_database()
                self.stats['last_backup'] = time.time()

            # Check risk limits
            account = self.mt5_client.get_account_info()
            if account:
                balance = account.get('balance', 0)

                # Check if should halt
                should_halt, reason = self.risk_manager.should_halt_trading(balance)
                if should_halt:
                    self.logger.error(f"🚨 Risk limit reached: {reason}")
                    self._enter_safe_mode()

                    if self.telegram.config.enabled:
                        self.telegram.notify_risk_limit_reached_sync(
                            'auto_halt',
                            {'reason': reason, 'balance': balance}
                        )

        except Exception as e:
            self.logger.error(f"Error in maintenance: {e}")

    def _log_status(self):
        """Log current status"""
        try:
            uptime = (datetime.now(timezone.utc) - self.stats['start_time']).total_seconds()
            hours = int(uptime // 3600)
            minutes = int((uptime % 3600) // 60)

            account = self.mt5_client.get_account_info()
            positions = len(self.mt5_client.get_positions(symbol=self.config.get('symbol')))

            self.logger.info(
                f"📊 Status - Uptime: {hours}h {minutes}m | "
                f"Signals: {self.stats['signals_generated']} (filtered: {self.stats['signals_filtered']}) | "
                f"Orders: {self.stats['orders_placed']} | "
                f"Positions: {positions} | "
                f"Balance: ${account.get('balance', 0):.2f} | "
                f"Errors: {self.stats['errors']}"
            )

        except Exception as e:
            self.logger.error(f"Error logging status: {e}")

    def _enter_safe_mode(self):
        """Enter safe mode"""
        try:
            self.logger.warning("⚠️ Entering safe mode")

            self.order_manager.cancel_all_pending("Safe mode activated")

            if self.config.get('close_on_safe_mode', False):
                # Close all positions
                positions = self.mt5_client.get_positions(symbol=self.config.get('symbol'))
                for pos in positions:
                    if pos.get('magic') == self.config.get('magic', 0):
                        self.mt5_client.close_position(pos['ticket'])

            self.running = False

        except Exception as e:
            self.logger.error(f"Error entering safe mode: {e}")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.shutdown_requested = True
        self.running = False

    def shutdown(self):
        """Graceful shutdown"""
        try:
            self.logger.info("Shutting down bot...")

            if self.order_manager:
                self.order_manager.cancel_all_pending("Bot shutdown")

            self._log_final_stats()

            if self.mt5_client:
                self.mt5_client.shutdown()

            self.logger.info("✅ Bot shutdown complete")

        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

    def _log_final_stats(self):
        """Log final statistics"""
        try:
            self.logger.info("=" * 80)
            self.logger.info("📊 FINAL STATISTICS")
            self.logger.info("=" * 80)
            self.logger.info(f"Signals Generated: {self.stats['signals_generated']}")
            self.logger.info(f"Signals Filtered: {self.stats['signals_filtered']}")
            self.logger.info(f"Orders Placed: {self.stats['orders_placed']}")
            self.logger.info(f"Positions Modified: {self.stats['positions_modified']}")
            self.logger.info(f"Errors: {self.stats['errors']}")

            # Get performance stats
            perf_stats = self.persistence.get_performance_stats(days=1)
            self.logger.info(f"Daily Trades: {perf_stats.get('total_trades', 0)}")
            self.logger.info(f"Win Rate: {perf_stats.get('win_rate', 0):.1f}%")
            self.logger.info(f"Net P&L: ${perf_stats.get('net_profit', 0):.2f}")
            self.logger.info("=" * 80)

        except Exception as e:
            self.logger.error(f"Error logging final stats: {e}")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Advanced Professional Trading Bot')
    parser.add_argument('--config', default='config_small_capital.yaml',
                       help='Path to configuration file')
    parser.add_argument('--mode', choices=['dry_run', 'demo', 'live'],
                       help='Override mode from config')
    parser.add_argument('--test', action='store_true',
                       help='Run in test mode (single analysis cycle)')

    args = parser.parse_args()

    # Create bot
    bot = AdvancedTradingBot(args.config)

    # Override mode
    if args.mode:
        bot.config['mode'] = args.mode
        bot.logger.info(f"Mode overridden to: {args.mode}")

    # Run
    if args.test:
        bot.logger.info("Running in test mode")
        if bot.initialize():
            bot._perform_analysis()
            bot.shutdown()
    else:
        bot.run()


if __name__ == '__main__':
    main()
