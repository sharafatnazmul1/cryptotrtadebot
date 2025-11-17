"""
Telegram Notification System
Sends real-time alerts and performance updates to Telegram
"""

import logging
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass

try:
    from telegram import Bot, Update
    from telegram.ext import Application, CommandHandler, ContextTypes
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logging.warning("python-telegram-bot not available. Install with: pip install python-telegram-bot")

logger = logging.getLogger(__name__)


@dataclass
class NotificationConfig:
    """Notification configuration"""
    bot_token: str
    chat_id: str
    enabled: bool = True
    notify_signals: bool = True
    notify_trades: bool = True
    notify_errors: bool = True
    notify_daily_summary: bool = True


class TelegramNotifier:
    """
    Professional Telegram notification system for trading bot
    Sends alerts for signals, trades, errors, and daily summaries
    """

    def __init__(self, config: NotificationConfig):
        """Initialize Telegram notifier"""
        self.config = config
        self.bot: Optional[Bot] = None
        self.application: Optional[Application] = None

        if not TELEGRAM_AVAILABLE:
            logger.warning("Telegram notifications disabled - library not installed")
            self.config.enabled = False
            return

        if not config.bot_token or not config.chat_id:
            logger.warning("Telegram bot token or chat ID not configured")
            self.config.enabled = False
            return

        try:
            self.bot = Bot(token=config.bot_token)
            logger.info("Telegram notifier initialized")
        except Exception as e:
            logger.error(f"Error initializing Telegram bot: {e}")
            self.config.enabled = False

    async def send_message(self, message: str, parse_mode: str = 'HTML'):
        """Send a message to Telegram"""
        try:
            if not self.config.enabled or not self.bot:
                return

            await self.bot.send_message(
                chat_id=self.config.chat_id,
                text=message,
                parse_mode=parse_mode
            )

        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")

    def send_message_sync(self, message: str, parse_mode: str = 'HTML'):
        """Synchronous wrapper for sending messages"""
        try:
            if not self.config.enabled:
                return

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.send_message(message, parse_mode))
            loop.close()

        except Exception as e:
            logger.error(f"Error in sync message send: {e}")

    async def notify_bot_started(self, bot_name: str, config_summary: Dict):
        """Notify that bot has started"""
        try:
            if not self.config.enabled:
                return

            message = f"""
🚀 <b>{bot_name} Started</b>

⏰ Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

📊 <b>Configuration:</b>
• Symbols: {', '.join(config_summary.get('symbols', []))}
• Risk per trade: {config_summary.get('risk_pct', 0)}%
• Max daily loss: {config_summary.get('max_daily_loss', 0)}%
• Max positions: {config_summary.get('max_positions', 0)}

✅ Bot is now actively trading
"""

            await self.send_message(message)

        except Exception as e:
            logger.error(f"Error sending bot started notification: {e}")

    async def notify_signal_generated(self, signal: Dict):
        """Notify about new trading signal"""
        try:
            if not self.config.enabled or not self.config.notify_signals:
                return

            side_emoji = "🟢" if signal['side'] == 'BUY' else "🔴"

            message = f"""
{side_emoji} <b>New Signal Generated</b>

📈 <b>Symbol:</b> {signal['symbol']}
📍 <b>Side:</b> {signal['side']}
💰 <b>Entry:</b> {signal['entry_price']:.5f}
🛑 <b>Stop Loss:</b> {signal['sl_price']:.5f}
🎯 <b>Take Profit:</b> {signal['tp_price']:.5f}

📊 <b>Analysis:</b>
• Signal Score: {signal.get('signal_score', 0)}/10
• RR Ratio: {signal.get('rr_ratio', 0):.2f}
• Zone Type: {signal.get('zone_type', 'N/A')}
• HTF Trend: {signal.get('htf_trend', 'N/A')}

⏰ {datetime.utcnow().strftime('%H:%M:%S')} UTC
"""

            await self.send_message(message)

        except Exception as e:
            logger.error(f"Error sending signal notification: {e}")

    async def notify_trade_opened(self, trade: Dict):
        """Notify about opened trade"""
        try:
            if not self.config.enabled or not self.config.notify_trades:
                return

            side_emoji = "🟢" if trade['side'] == 'BUY' else "🔴"

            message = f"""
{side_emoji} <b>Trade Opened</b>

📈 <b>Symbol:</b> {trade['symbol']}
🎫 <b>Ticket:</b> {trade['ticket']}
📍 <b>Side:</b> {trade['side']}
📊 <b>Volume:</b> {trade['volume']:.2f} lots

💰 <b>Entry:</b> {trade['entry_price']:.5f}
🛑 <b>SL:</b> {trade['stop_loss']:.5f}
🎯 <b>TP:</b> {trade['take_profit']:.5f}

💵 <b>Risk:</b> ${trade.get('risk_amount', 0):.2f} ({trade.get('risk_pct', 0):.2f}%)
📈 <b>Potential Profit:</b> ${trade.get('potential_profit', 0):.2f}

⏰ {datetime.utcnow().strftime('%H:%M:%S')} UTC
"""

            await self.send_message(message)

        except Exception as e:
            logger.error(f"Error sending trade opened notification: {e}")

    async def notify_trade_closed(self, trade: Dict):
        """Notify about closed trade"""
        try:
            if not self.config.enabled or not self.config.notify_trades:
                return

            profit = trade.get('profit', 0)
            profit_emoji = "✅" if profit > 0 else "❌"

            message = f"""
{profit_emoji} <b>Trade Closed</b>

📈 <b>Symbol:</b> {trade['symbol']}
🎫 <b>Ticket:</b> {trade['ticket']}
📍 <b>Side:</b> {trade['side']}

💰 <b>Entry:</b> {trade.get('entry_price', 0):.5f}
🏁 <b>Exit:</b> {trade.get('exit_price', 0):.5f}

💵 <b>Profit:</b> ${profit:.2f} ({trade.get('profit_pct', 0):.2f}%)
⏱ <b>Duration:</b> {trade.get('duration_hours', 0):.1f} hours

<b>Reason:</b> {trade.get('close_reason', 'N/A')}

⏰ {datetime.utcnow().strftime('%H:%M:%S')} UTC
"""

            await self.send_message(message)

        except Exception as e:
            logger.error(f"Error sending trade closed notification: {e}")

    async def notify_position_modified(self, modification: Dict):
        """Notify about position modification (SL/TP change, partial close)"""
        try:
            if not self.config.enabled:
                return

            mod_type = modification.get('type', 'unknown')
            emoji_map = {
                'break_even': '🔒',
                'trailing_stop': '📈',
                'partial_close': '💰'
            }
            emoji = emoji_map.get(mod_type, '🔄')

            message = f"""
{emoji} <b>Position Modified</b>

🎫 <b>Ticket:</b> {modification['ticket']}
📈 <b>Symbol:</b> {modification['symbol']}

<b>Modification:</b> {mod_type.replace('_', ' ').title()}

"""

            if mod_type == 'trailing_stop':
                message += f"🛑 <b>New SL:</b> {modification.get('new_sl', 0):.5f}\n"
                message += f"📊 <b>Profit:</b> {modification.get('profit_pct', 0):.2f}%\n"

            elif mod_type == 'break_even':
                message += f"🔒 <b>SL → Break-Even:</b> {modification.get('new_sl', 0):.5f}\n"

            elif mod_type == 'partial_close':
                message += f"💰 <b>Closed:</b> {modification.get('closed_volume', 0):.2f} lots\n"
                message += f"💵 <b>Profit:</b> ${modification.get('profit', 0):.2f}\n"

            message += f"\n⏰ {datetime.utcnow().strftime('%H:%M:%S')} UTC"

            await self.send_message(message)

        except Exception as e:
            logger.error(f"Error sending position modified notification: {e}")

    async def notify_error(self, error_type: str, error_message: str, severity: str = 'ERROR'):
        """Notify about errors"""
        try:
            if not self.config.enabled or not self.config.notify_errors:
                return

            emoji_map = {
                'CRITICAL': '🚨',
                'ERROR': '⚠️',
                'WARNING': '⚡'
            }
            emoji = emoji_map.get(severity, '⚠️')

            message = f"""
{emoji} <b>{severity}: {error_type}</b>

<b>Message:</b>
{error_message}

⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
"""

            await self.send_message(message)

        except Exception as e:
            logger.error(f"Error sending error notification: {e}")

    async def notify_daily_summary(self, summary: Dict):
        """Send daily performance summary"""
        try:
            if not self.config.enabled or not self.config.notify_daily_summary:
                return

            total_pnl = summary.get('total_pnl', 0)
            pnl_emoji = "📈" if total_pnl > 0 else "📉"

            message = f"""
📊 <b>Daily Performance Summary</b>

{pnl_emoji} <b>Total P&L:</b> ${total_pnl:.2f} ({summary.get('pnl_pct', 0):.2f}%)

📈 <b>Trading Stats:</b>
• Trades: {summary.get('total_trades', 0)}
• Wins: {summary.get('winning_trades', 0)} ({summary.get('win_rate', 0):.1f}%)
• Losses: {summary.get('losing_trades', 0)}

💰 <b>Performance:</b>
• Avg Win: ${summary.get('avg_win', 0):.2f}
• Avg Loss: ${summary.get('avg_loss', 0):.2f}
• Profit Factor: {summary.get('profit_factor', 0):.2f}
• Best Trade: ${summary.get('best_trade', 0):.2f}
• Worst Trade: ${summary.get('worst_trade', 0):.2f}

💼 <b>Account:</b>
• Balance: ${summary.get('balance', 0):.2f}
• Equity: ${summary.get('equity', 0):.2f}
• Max Drawdown: {summary.get('max_drawdown', 0):.2f}%

📅 {summary.get('date', datetime.utcnow().strftime('%Y-%m-%d'))}
"""

            await self.send_message(message)

        except Exception as e:
            logger.error(f"Error sending daily summary: {e}")

    async def notify_risk_limit_reached(self, limit_type: str, details: Dict):
        """Notify about risk limits being reached"""
        try:
            if not self.config.enabled:
                return

            message = f"""
🚨 <b>RISK LIMIT REACHED</b>

⚠️ <b>Limit Type:</b> {limit_type}

<b>Details:</b>
• Current Loss: {details.get('current_loss_pct', 0):.2f}%
• Limit: {details.get('limit_pct', 0):.2f}%
• Balance: ${details.get('balance', 0):.2f}

🛑 <b>Action:</b> Trading halted

⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
"""

            await self.send_message(message)

        except Exception as e:
            logger.error(f"Error sending risk limit notification: {e}")

    async def notify_market_regime_change(self, old_regime: str, new_regime: str, confidence: float):
        """Notify about market regime change"""
        try:
            if not self.config.enabled:
                return

            message = f"""
🔄 <b>Market Regime Change</b>

📊 <b>Old Regime:</b> {old_regime.replace('_', ' ').title()}
📊 <b>New Regime:</b> {new_regime.replace('_', ' ').title()}
📈 <b>Confidence:</b> {confidence:.1%}

⏰ {datetime.utcnow().strftime('%H:%M:%S')} UTC
"""

            await self.send_message(message)

        except Exception as e:
            logger.error(f"Error sending regime change notification: {e}")

    def notify_bot_started_sync(self, bot_name: str, config_summary: Dict):
        """Synchronous wrapper"""
        self.send_message_sync(f"🚀 <b>{bot_name} Started</b>\n\n✅ Bot is now actively trading")

    def notify_signal_generated_sync(self, signal: Dict):
        """Synchronous wrapper"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.notify_signal_generated(signal))
            loop.close()
        except Exception as e:
            logger.error(f"Error in sync signal notification: {e}")

    def notify_trade_opened_sync(self, trade: Dict):
        """Synchronous wrapper"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.notify_trade_opened(trade))
            loop.close()
        except Exception as e:
            logger.error(f"Error in sync trade opened notification: {e}")

    def notify_trade_closed_sync(self, trade: Dict):
        """Synchronous wrapper"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.notify_trade_closed(trade))
            loop.close()
        except Exception as e:
            logger.error(f"Error in sync trade closed notification: {e}")

    def notify_error_sync(self, error_type: str, error_message: str, severity: str = 'ERROR'):
        """Synchronous wrapper"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.notify_error(error_type, error_message, severity))
            loop.close()
        except Exception as e:
            logger.error(f"Error in sync error notification: {e}")

    def notify_position_modified_sync(self, modification: Dict):
        """Synchronous wrapper"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.notify_position_modified(modification))
            loop.close()
        except Exception as e:
            logger.error(f"Error in sync position modification notification: {e}")

    def notify_risk_limit_reached_sync(self, limit_type: str, details: Dict):
        """Synchronous wrapper"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.notify_risk_limit_reached(limit_type, details))
            loop.close()
        except Exception as e:
            logger.error(f"Error in sync risk limit notification: {e}")
