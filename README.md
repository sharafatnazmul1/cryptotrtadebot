# 🚀 Professional Crypto Trading Bot

## Hedge Fund-Grade SMC/ICT Trading System

A professional-grade cryptocurrency trading bot built on **Smart Money Concepts (SMC)** and **Inner Circle Trader (ICT)** principles. This system implements institutional trading strategies used by hedge funds and professional traders.

> **⚠️ CRITICAL UPDATE (Nov 14, 2025)**: Comprehensive audit completed! Critical lot calculation bug fixed. Small capital traders ($500-$2000): See **`QUICK_START_SMALL_CAPITAL.md`** for optimized setup. Everyone: Review **`AUDIT_RESULTS.md`** for details.

> **🚀 FINAL PRODUCTION RELEASE**: This bot is now **FULLY INTEGRATED** and **READY TO RUN**. All advanced modules working together. See **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** for complete setup instructions.

---

## 🎯 Key Features

### Advanced SMC/ICT Implementation
- ✅ **Order Blocks** - Institutional supply/demand zones
- ✅ **Fair Value Gaps (FVG)** - Price imbalances
- ✅ **Liquidity Pools** - Equal highs/lows targeting
- ✅ **Premium/Discount Zones** - Optimal entry areas
- ✅ **Optimal Trade Entry (OTE)** - 62-79% Fibonacci retracements
- ✅ **Break of Structure (BOS)** - Trend continuation
- ✅ **Change of Character (CHoCH)** - Market reversals
- ✅ **Breaker Blocks** - Failed order blocks
- ✅ **Silver Bullet Timing** - ICT Kill Zones
- ✅ **Institutional Order Flow** - Smart money tracking
- ✅ **Power of Three** - Accumulation, Manipulation, Distribution
- ✅ **Volume Profile** - POC, VAH, VAL analysis
- ✅ **Inducement Detection** - Fake breakout identification

### Professional Risk Management
- ✅ **Kelly Criterion** - Mathematically optimal position sizing
- ✅ **Portfolio-Level Risk** - Diversification management
- ✅ **Correlation Analysis** - Multi-pair exposure control
- ✅ **Adaptive Risk Scaling** - Performance-based adjustments
- ✅ **Multi-Timeframe Loss Limits** - Daily/Weekly/Monthly caps
- ✅ **Maximum Drawdown Protection** - Account preservation
- ✅ **Consecutive Loss Halting** - Automatic trading pause

### Advanced Position Management
- ✅ **Trailing Stops** - Dynamic profit protection
- ✅ **Break-Even Management** - Risk-free positioning
- ✅ **Partial Profit Taking** - Multiple exit strategy
- ✅ **Time-Based Exits** - Duration limits
- ✅ **Dynamic SL/TP** - Market-adapted targets

### Machine Learning Integration
- ✅ **Signal Quality Prediction** - ML-based filtering
- ✅ **Market Regime Classification** - Adaptive strategies
- ✅ **Feature Importance Analysis** - Strategy optimization
- ✅ **Auto-Retraining** - Continuous improvement

### Small Capital Optimization
- ✅ **Account Tier Classification** - Micro/Small/Medium/Standard
- ✅ **Dynamic Risk Adjustment** - 0.3-1.0% by account size
- ✅ **Quality-First Filtering** - Higher thresholds for small accounts
- ✅ **Fast Profit Protection** - Break-even at 0.3%, partials at 0.5%
- ✅ **Conservative Loss Limits** - 1.5-2% daily for small accounts

### Professional Monitoring
- ✅ **Telegram Notifications** - Real-time alerts
- ✅ **Daily Performance Reports** - Automated summaries
- ✅ **Error Alerting** - Instant notifications
- ✅ **Trade Journaling** - Complete audit trail

---

## 📋 System Requirements

- **Python**: 3.9+
- **MetaTrader 5**: Latest version
- **Broker**: Exness (or any MT5 broker supporting crypto)
- **OS**: Windows, Linux, or MacOS
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 2GB free space

---

## 🛠️ Installation

### 1. Clone Repository
```bash
git clone https://github.com/sharafatnazmul1/cryptotradingbot.git
cd cryptotradingbot
```

### 2. Create Virtual Environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
```bash
cp .env.example .env
```

Edit `.env` file with your credentials:
```env
# MetaTrader 5
MT5_LOGIN=your_account_number
MT5_PASSWORD=your_password
MT5_SERVER=Exness-MT5Trial17
MT5_PATH=/path/to/terminal64.exe

# Telegram (Optional)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Trading Mode
TRADING_MODE=demo  # Use 'demo' for testing, 'live' for real trading
```

### 5. Choose Configuration File

**For Small Accounts ($500-$2000):**
Use `config_small_capital.yaml` - Optimized for small capital with conservative settings

**For Larger Accounts ($2000+):**
Use `config_crypto.yaml` - Full-featured configuration

---

## 🚀 Usage

### Quick Start - Testing Connection

**ALWAYS test connection first:**
```bash
python main_advanced.py --config config_small_capital.yaml --test
```

This will:
- Initialize MT5 connection
- Verify credentials
- Check symbol availability
- Run one analysis cycle
- Shutdown cleanly

**Expected output:**
```
🚀 ADVANCED PROFESSIONAL TRADING BOT STARTING
✓ Initializing components...
✓ Initializing MT5 client...
  Account tier: small ($1000.00)
✅ ALL COMPONENTS INITIALIZED SUCCESSFULLY
```

### Start Bot - Demo Mode (REQUIRED FIRST)

**Start with demo mode for 2 weeks minimum:**
```bash
python main_advanced.py --config config_small_capital.yaml
```

The bot will:
- Use `mode: demo` from config file
- Connect to your demo MT5 account
- Start analyzing markets
- Generate and execute signals
- Manage positions automatically

### Command Line Options

```bash
# Use specific config file
python main_advanced.py --config config_small_capital.yaml

# Override mode from config
python main_advanced.py --config config_small_capital.yaml --mode demo
python main_advanced.py --config config_small_capital.yaml --mode live

# Test connection only
python main_advanced.py --config config_small_capital.yaml --test
```

**Available Modes:**
- `dry_run` - Generates signals but doesn't place orders
- `demo` - Places orders on demo account (recommended for testing)
- `live` - Places orders on live account (use after 2 weeks demo success)

### Configuration Files

**config_small_capital.yaml** (Recommended for $500-$2000)
```bash
python main_advanced.py --config config_small_capital.yaml
```

**config_crypto.yaml** (For larger accounts $2000+)
```bash
python main_advanced.py --config config_crypto.yaml
```

**Note:** The bot currently focuses on BTCUSD (single pair) for maximum profitability with small capital. Multi-symbol trading will be added in future updates.

### Stopping the Bot

**Graceful Shutdown (Recommended):**
```bash
# Press Ctrl+C in the terminal
# The bot will:
# 1. Cancel pending orders
# 2. Log final statistics
# 3. Close connections cleanly
```

**Force Stop (Emergency):**
```bash
# Find the process
ps aux | grep main_advanced

# Kill it
kill <PID>
```

### Monitoring the Bot

**Check Logs:**
```bash
# View today's log
tail -f logs/trading_bot_$(date +%Y%m%d).log

# Search for errors
grep ERROR logs/*.log

# Search for trades
grep "Order placed" logs/*.log
```

**Check Performance:**
```bash
# View trade history
cat data/trades.csv | tail -20

# View signal history
cat data/signals.csv | tail -20
```

**Monitor in Real-Time:**
- Enable Telegram notifications in config
- Set `telegram.enabled: true`
- Get instant alerts for signals, trades, errors

---

## 📊 System Architecture

### Core Modules

#### 1. **indicators_advanced.py**
Advanced SMC/ICT indicators:
- Premium/Discount zones
- Liquidity pool detection
- BOS/CHoCH identification
- Institutional order flow
- Volume profile calculation
- Silver bullet timing
- Power of Three analysis

#### 2. **risk_advanced.py**
Professional risk management:
- Kelly Criterion calculation
- Portfolio-level exposure
- Adaptive position sizing
- Multi-timeframe loss limits
- Drawdown protection

#### 3. **position_manager_advanced.py**
Position lifecycle management:
- Trailing stop logic
- Break-even activation
- Partial profit taking
- Time-based exits
- Dynamic SL/TP modification

#### 4. **ml_signal_filter.py**
Machine learning integration:
- Signal quality prediction
- Market regime classification
- Feature extraction
- Model training/retraining
- Performance analytics

#### 5. **small_capital_optimizer.py**
Small account optimization:
- Account tier classification (micro/small/medium)
- Dynamic risk by account size
- Higher quality signal filtering
- Optimized position management
- Conservative loss limits

#### 6. **telegram_notifier.py**
Real-time notifications:
- Trade alerts
- Signal notifications
- Error reporting
- Daily summaries
- Risk limit warnings

---

## 🎓 Trading Strategy

### Signal Generation Process

1. **Multi-Timeframe Analysis**
   - H1: Overall trend direction
   - M15: Market structure and zones
   - M5: Entry refinement
   - M1: Precise entry timing

2. **Zone Identification**
   - Order Blocks (institutional footprints)
   - Fair Value Gaps (imbalances)
   - Premium/Discount areas
   - Liquidity pools

3. **Confluence Scoring**
   - HTF trend alignment: 3 points
   - Market structure: 2 points
   - Zone quality: 3 points
   - Liquidity sweep: 2 points
   - Order flow: 2 points
   - Kill zone timing: 1 point
   - ML confidence: 2 points
   - **Minimum required: 6/15 points**

4. **Entry Optimization**
   - OTE zones (62-79% Fibonacci)
   - Silver bullet timing
   - Premium for sells, discount for buys
   - ML signal filtering

5. **Risk Management**
   - Kelly Criterion position sizing
   - Correlation-adjusted risk
   - Multi-symbol exposure control
   - Dynamic loss limits

6. **Exit Strategy**
   - Initial TP at 3:1 RR
   - Trailing stops after 1% profit
   - Partial profits at 1%, 2%, 3%
   - Break-even at 0.5% profit
   - Max hold: 24 hours

---

## 📈 Performance Optimization

### Backtesting
```bash
python main.py --backtest \
  --start 2023-01-01 \
  --end 2024-12-31 \
  --config config_crypto.yaml \
  --initial-balance 10000
```

### Walk-Forward Optimization
```python
# In config_crypto.yaml
machine_learning:
  enabled: true
  auto_retrain: true
  retrain_interval_trades: 20
```

### Live Performance Monitoring
- Daily P&L tracking
- Win rate calculation
- Sharpe/Sortino ratios
- Maximum drawdown
- Profit factor
- Kelly percentage updates

---

## ⚙️ Configuration Guide

### Risk Settings (Conservative)
```yaml
risk:
  risk_pct_per_trade: 0.3  # 0.3% per trade
  max_daily_loss_pct: 3.0  # 3% daily limit
  max_concurrent_positions: 2
```

### Risk Settings (Aggressive)
```yaml
risk:
  risk_pct_per_trade: 1.0  # 1% per trade
  max_daily_loss_pct: 7.0  # 7% daily limit
  max_concurrent_positions: 5
```

### ICT Purist Settings
```yaml
smc_ict:
  killzones:
    only_trade_killzones: true  # Trade ONLY in kill zones
  premium_discount:
    use_ote: true  # Strict OTE entries only
```

---

## 🔒 Security Best Practices

1. **Never commit credentials** to git
2. **Use .env file** for sensitive data
3. **Enable 2FA** on MT5 account
4. **Start with paper trading** mode
5. **Test thoroughly** before live trading
6. **Monitor daily** for anomalies
7. **Keep backups** of configuration
8. **Use VPS** for 24/7 operation

---

## 📱 Telegram Setup

### 1. Create Telegram Bot
1. Message @BotFather on Telegram
2. Send `/newbot`
3. Follow instructions
4. Copy bot token

### 2. Get Chat ID
1. Message your bot
2. Visit: `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Find your chat ID
4. Add to `.env` file

### 3. Enable Notifications
```yaml
# In config_crypto.yaml
telegram:
  enabled: true
  notify_signals: true
  notify_trades: true
  notify_daily_summary: true
```

---

## 🐛 Troubleshooting

### MT5 Connection Issues
```bash
# Check MT5 is running
# Verify credentials in .env
# Ensure terminal allows algo trading
# Check firewall settings
```

### No Signals Generated
```bash
# Lower min_signal_score in config
# Check if in enabled trading session
# Verify symbols are available on broker
# Review logs for errors
```

### High Memory Usage
```bash
# Reduce max_training_samples
# Limit enabled symbols
# Decrease lookback periods
```

### ML Models Not Training
```bash
# Install ML dependencies:
pip install scikit-learn xgboost lightgbm

# Check min_training_samples met
# Verify sufficient trade history
```

---

## 📊 Performance Metrics

### Target Metrics (Monthly)
- **Win Rate**: 55-65%
- **Profit Factor**: 1.8-2.5
- **Sharpe Ratio**: > 1.5
- **Max Drawdown**: < 15%
- **Monthly Return**: 5-15%

### Risk Metrics
- **Risk per Trade**: 0.5-1%
- **Max Daily Loss**: 5%
- **Max Positions**: 3
- **Leverage**: Dynamic (broker dependent)

---

## 🤝 Contributing

This is a professional trading system. Modifications should be:
1. Thoroughly tested
2. Backtested over multiple periods
3. Risk-managed appropriately
4. Documented properly

---

## ⚠️ Disclaimer

**IMPORTANT**: Trading cryptocurrencies involves substantial risk of loss. This bot is provided for educational purposes. Past performance does not guarantee future results. Always:

- Start with paper trading
- Use risk management
- Never risk more than you can afford to lose
- Understand the strategies before trading
- Monitor the system regularly
- Keep sufficient account balance
- Test thoroughly before live deployment

**No guarantee of profit. Use at your own risk.**

---

## 📚 Resources

### ICT/SMC Education
- Inner Circle Trader YouTube Channel
- Smart Money Concepts courses
- Institutional order flow analysis
- Market maker manipulation studies

### Technical Resources
- MetaTrader 5 Python Documentation
- Telegram Bot API
- Machine Learning for Trading
- Quantitative Finance Textbooks

---

## 📧 Support

For issues and questions:
- Open GitHub issue
- Review logs in `./logs/`
- Check configuration settings
- Verify MT5 connection
- Test with paper trading first

---

## 🎯 Roadmap

### Future Enhancements
- [ ] Web-based dashboard
- [ ] Mobile app integration
- [ ] Multi-broker support
- [ ] Advanced ML models (LSTM, Transformer)
- [ ] Sentiment analysis integration
- [ ] On-chain metrics for crypto
- [ ] Portfolio optimization
- [ ] Strategy A/B testing
- [ ] Cloud deployment automation
- [ ] Real-time order book analysis

---

## 📄 License

This project is provided as-is for educational purposes.

---

## 🙏 Acknowledgments

- Inner Circle Trader (ICT) for SMC concepts
- The trading community for shared knowledge
- Open source contributors

---

**Built with ❤️ for professional traders**

**Trade Smart. Trade Safe. Trade Profitably.** 🚀