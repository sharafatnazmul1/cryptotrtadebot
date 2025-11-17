# Backtest System - Complete Guide

This comprehensive backtesting system allows you to test your trading bot's performance using real historical MT5 data **much faster** than live trading, without risking real money.

---

## 🚀 Quick Start

### 1. Basic Backtest (Last 30 Days)

```bash
python run_backtest.py \
  --start-date 2024-10-15 \
  --end-date 2024-11-15 \
  --balance 1000
```

### 2. Custom Configuration

```bash
python run_backtest.py \
  --config config_small_capital.yaml \
  --start-date 2024-01-01 \
  --end-date 2024-03-31 \
  --balance 5000 \
  --output-dir ./my_backtest_results
```

### 3. Verbose Mode (For Debugging)

```bash
python run_backtest.py \
  --start-date 2024-10-01 \
  --end-date 2024-11-01 \
  --balance 1000 \
  --verbose
```

---

## 📋 Command Line Options

| Option | Description | Default | Required |
|--------|-------------|---------|----------|
| `--config` | Configuration file | `config_small_capital.yaml` | No |
| `--start-date` | Start date (YYYY-MM-DD) | - | **Yes** |
| `--end-date` | End date (YYYY-MM-DD) | - | **Yes** |
| `--balance` | Initial account balance | `1000` | No |
| `--no-cache` | Don't use cached data | `False` | No |
| `--verbose`, `-v` | Verbose logging | `False` | No |
| `--output-dir` | Results output directory | `./backtest_results` | No |

---

## 🎯 What Gets Tested

The backtest system simulates **EVERYTHING** your bot does in live trading:

### ✅ Signal Generation
- All SMC/ICT indicators (Order Blocks, FVGs, Liquidity Pools, BOS/CHoCH)
- Multi-timeframe analysis (HTF, MTF, LTF)
- Kill zone detection
- Signal scoring and quality assessment

### ✅ Risk Management
- Kelly Criterion position sizing
- Small capital optimization (micro/small/medium/standard tiers)
- Daily/weekly/monthly loss limits
- Portfolio exposure limits
- Consecutive loss protection

### ✅ Position Management
- Trailing stops
- Break-even activation
- Partial profit taking
- Time-based exits

### ✅ ML Signal Filtering
- Signal quality prediction
- Market regime classification
- Confidence scoring

### ✅ Order Execution
- Realistic slippage simulation
- Commission calculation
- Spread modeling
- Stop loss / Take profit execution
- Pending order fills

---

## 📊 Output Files

After running a backtest, you'll get:

```
backtest_results/
├── report_20241115_120000.txt          # Human-readable report
├── results_20241115_120000.json        # Full results in JSON
├── equity_curve_20241115_120000.csv    # Equity over time
└── trades_20241115_120000.csv          # All closed trades
```

### Report Sections

1. **Backtest Summary**
   - Period, duration, balance, profit, return %

2. **Risk Metrics**
   - Maximum drawdown, drawdown duration, Sharpe ratio

3. **Trading Statistics**
   - Win rate, avg win/loss, profit factor, largest win/loss

4. **Signal Statistics**
   - Signals generated vs executed

5. **Monthly Performance**
   - Profit/loss breakdown by month

6. **Strategy Rating**
   - Overall score (0-100) with grade (A+, A, B, C, D, F)
   - Breakdown by: Profitability, Win Rate, Profit Factor, Risk Management, Consistency

7. **Recommendations**
   - Actionable suggestions based on performance

---

## 🔧 Backtest Configuration

### Setting Up config_backtest.yaml

You can customize backtest parameters in your config file:

```yaml
# Backtest-specific settings
backtest_slippage_pips: 2          # Simulated slippage (pips)
backtest_commission_per_lot: 0.0   # Commission per lot
backtest_spread_multiplier: 1.0    # Spread multiplier (1.0 = normal)
signal_check_interval: 5           # Check for signals every N bars
```

---

## 📈 Understanding Results

### Strategy Rating Criteria

**Profitability (20 points)**
- 100%+ return = 20 pts
- 50-100% = 15 pts
- 20-50% = 10 pts
- 0-20% = 5 pts
- Negative = 0 pts

**Win Rate (20 points)**
- 70%+ = 20 pts
- 60-70% = 15 pts
- 50-60% = 10 pts
- 40-50% = 5 pts
- <40% = 0 pts

**Profit Factor (20 points)**
- 3.0+ = 20 pts
- 2.0-3.0 = 15 pts
- 1.5-2.0 = 10 pts
- 1.0-1.5 = 5 pts
- <1.0 = 0 pts

**Risk Management (20 points)**
- Max DD ≤5% = 20 pts
- 5-10% = 15 pts
- 10-20% = 10 pts
- 20-30% = 5 pts
- >30% = 0 pts

**Consistency (20 points)**
- Sharpe ≥2.0 = 20 pts
- 1.5-2.0 = 15 pts
- 1.0-1.5 = 10 pts
- 0.5-1.0 = 5 pts
- <0.5 = 0 pts

### What to Look For

**Good Strategy:**
- ✅ Return >20% with <15% max drawdown
- ✅ Win rate 50-70%
- ✅ Profit factor >1.5
- ✅ Sharpe ratio >1.0
- ✅ Overall rating: B or higher

**Needs Work:**
- ⚠️ Win rate <45%
- ⚠️ Max drawdown >25%
- ⚠️ Profit factor <1.2
- ⚠️ Negative returns

---

## 🎨 Advanced Usage

### 1. Testing Different Time Periods

Test across multiple periods to validate consistency:

```bash
# Q1 2024
python run_backtest.py --start-date 2024-01-01 --end-date 2024-03-31 --balance 1000

# Q2 2024
python run_backtest.py --start-date 2024-04-01 --end-date 2024-06-30 --balance 1000

# Q3 2024
python run_backtest.py --start-date 2024-07-01 --end-date 2024-09-30 --balance 1000
```

### 2. Testing Different Capital Sizes

See how the strategy performs with different account tiers:

```bash
# Micro account
python run_backtest.py --start-date 2024-10-01 --end-date 2024-11-01 --balance 500

# Small account
python run_backtest.py --start-date 2024-10-01 --end-date 2024-11-01 --balance 1500

# Medium account
python run_backtest.py --start-date 2024-10-01 --end-date 2024-11-01 --balance 5000
```

### 3. Walk-Forward Testing

Test on one period, apply to next:

```bash
# Training period (Jan-Mar)
python run_backtest.py --start-date 2024-01-01 --end-date 2024-03-31

# Testing period (Apr-Jun) - see if strategy still works
python run_backtest.py --start-date 2024-04-01 --end-date 2024-06-30
```

### 4. Clearing Cache

If you update data or want fresh fetches:

```bash
python run_backtest.py --start-date 2024-10-01 --end-date 2024-11-01 --no-cache
```

Or manually:

```bash
rm -rf backtest_cache/*
```

---

## 🐛 Troubleshooting

### "MT5 initialization failed"
- **Solution**: Make sure MT5 is installed and running
- Check `.env` file has correct credentials
- Verify MT5 server is accessible

### "No data received from MT5"
- **Solution**: Symbol might not have history for that period
- Try a more recent date range
- Verify symbol name is correct in config

### "Failed to fetch historical data"
- **Solution**: Date range might be too far back
- MT5 might not have data for that symbol/timeframe
- Try with `--no-cache` to fetch fresh data

### Memory errors with long backtests
- **Solution**: Test shorter periods (e.g., 1-3 months at a time)
- Increase `signal_check_interval` in config
- Close other applications

---

## 💡 Best Practices

### 1. **Start Small**
Test 1-2 months first to validate the system works

### 2. **Multiple Time Periods**
Test at least 3 different time periods to ensure consistency

### 3. **Compare Market Conditions**
Test during:
- Trending markets
- Ranging markets
- High volatility periods
- Low volatility periods

### 4. **Realistic Expectations**
- Backtest shows **potential**, not guarantees
- Always test on demo before live
- Past performance ≠ future results

### 5. **Use Walk-Forward Testing**
- Train on past data
- Validate on future data
- This prevents overfitting

---

## 📊 Example Workflow

### Complete Testing Process:

```bash
# 1. Quick test (last 30 days)
python run_backtest.py --start-date 2024-10-15 --end-date 2024-11-15 --balance 1000

# 2. Review results
cat backtest_results/report_*.txt

# 3. If looks good, test longer period (3 months)
python run_backtest.py --start-date 2024-08-01 --end-date 2024-11-01 --balance 1000

# 4. Test with different capital
python run_backtest.py --start-date 2024-08-01 --end-date 2024-11-01 --balance 5000

# 5. If all tests good, run on demo
python main_advanced.py --config config_small_capital.yaml --mode demo

# 6. After demo success (1-2 weeks), consider live
python main_advanced.py --config config_small_capital.yaml --mode live
```

---

## ⚡ Performance Tips

### Speed Up Backtests:

1. **Use Cache**: Don't use `--no-cache` unless necessary
2. **Increase Interval**: Set `signal_check_interval: 10` in config
3. **Shorter Periods**: Test 1-3 months at a time
4. **Limit Timeframes**: Use fewer timeframes if possible

### Accuracy vs Speed:

```yaml
# Faster (good for initial testing)
signal_check_interval: 10    # Check every 10 bars

# More accurate (for final validation)
signal_check_interval: 1     # Check every bar
```

---

## 📁 File Structure

```
cryptotradingbot/
├── run_backtest.py          # Main backtest runner
├── backtest_engine.py       # Backtest engine (core)
├── backtest_broker.py       # Simulated broker
├── backtest_data.py         # Data manager
├── backtest_analytics.py    # Analytics & reporting
├── backtest_cache/          # Cached historical data
│   └── *.pkl
├── backtest_results/        # Results output
│   ├── report_*.txt
│   ├── results_*.json
│   ├── equity_curve_*.csv
│   └── trades_*.csv
└── logs/                    # Backtest logs
    └── backtest_*.log
```

---

## 🎓 Next Steps

After successful backtests:

1. ✅ **Backtest passed** (Rating B+ or higher)
   → Test on **demo** account for 1-2 weeks

2. ✅ **Demo successful** (similar to backtest)
   → Start with **small live** account

3. ✅ **Live profitable** (1+ months)
   → Gradually increase position sizes

**Remember**: Even with great backtest results, always start with demo trading first!

---

## 🆘 Support

If you encounter issues:

1. Check logs in `./logs/backtest_*.log`
2. Run with `--verbose` for detailed output
3. Verify MT5 connection works
4. Test with a short date range first
5. Clear cache and try again

---

**Happy Backtesting! 🚀**
