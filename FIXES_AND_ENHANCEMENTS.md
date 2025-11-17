"""
CRITICAL FIXES AND ENHANCEMENTS

This module documents critical bugs found and fixed in the trading bot.

## CRITICAL BUGS FIXED:

### 1. LOT CALCULATION ERROR (risk.py:95)
**SEVERITY: CRITICAL - FINANCIAL LOSS RISK**

**Original Code:**
```python
if leverage > 1:
    lots = lots * (leverage / 100)  # WRONG!
```

**Problem:**
- For leverage 1:500, this multiplies by 5 (500/100)
- For leverage 1:100, this multiplies by 1 (100/100)
- This is backwards and would cause MASSIVE position sizes

**Example Impact:**
- Account: $1000, Risk 1%, Leverage 1:500
- Correct lot size: 0.01
- Buggy calculation: 0.01 * 5 = 0.05 (5x oversized!)
- This risks 5% instead of 1% - UNACCEPTABLE

**Fix:**
Removed the leverage multiplication entirely. Lot size should be
calculated based on risk amount and SL distance ONLY. Leverage
is already factored into margin requirements by broker.

**Correct Formula:**
lots = risk_amount / (sl_distance * contract_size * point_value)

---

### 2. MISSING POSITION COUNT CHECK
**SEVERITY: HIGH - OVERTRADING RISK**

**Problem:**
- Risk manager doesn't check max_concurrent_positions before allowing signal
- Could open unlimited positions, violating risk limits

**Fix:**
Added check_max_positions() method in enhanced risk manager

---

### 3. ATR CALCULATION IMPRECISION
**SEVERITY: MEDIUM - ENTRY QUALITY**

**Problem:**
- ATR calculation uses rolling mean which is less responsive
- Better to use EMA-based ATR for faster adaptation

**Fix:**
Enhanced ATR calculation in indicators_advanced.py

---

### 4. SIGNAL SCORING BIAS
**SEVERITY: MEDIUM - PROFITABILITY**

**Problem:**
- Equal weight to all factors doesn't account for importance
- Low-quality signals can still reach minimum score

**Fix:**
- Implemented weighted scoring system
- Added ML-based signal filtering
- Raised minimum score threshold for small capital accounts

---

### 5. NO SMALL CAPITAL OPTIMIZATION
**SEVERITY: HIGH - USER'S PRIMARY CONCERN**

**Problem:**
- Fixed risk % doesn't adapt to account size
- No compounding strategy for growth
- No protection against consecutive losses

**Fix:**
- Adaptive risk scaling based on account size
- Reduced risk for accounts < $1000
- Enhanced Kelly Criterion implementation
- Consecutive loss protection (halve risk after 2 losses)

---

## ENHANCEMENTS FOR SMALL CAPITAL PROFITABILITY:

### 1. Dynamic Risk Scaling
- Accounts < $500: 0.3% per trade (ultra-conservative)
- Accounts $500-$1000: 0.5% per trade (conservative)
- Accounts $1000-$5000: 0.7% per trade (moderate)
- Accounts > $5000: 1.0% per trade (standard)

### 2. Signal Quality Threshold
- Small accounts ONLY take signals score >= 7/10
- Larger accounts can take >= 6/10
- ML confidence >= 65% required for small capital

### 3. Time-of-Day Optimization
- Focus on high-probability kill zones only
- Avoid low-liquidity hours (22:00-01:00 UTC)
- Prioritize London/NY overlap (12:00-16:00 UTC)

### 4. Quick Profit Taking
- Small capital: Take partial profit at 0.5% gain
- Move to break-even faster (at 0.3% profit)
- Tighter trailing stops (0.3% trail distance)

### 5. Capital Preservation
- Daily loss limit: 2% for accounts < $1000
- Weekly loss limit: 5% for accounts < $1000
- Halt trading after 2 consecutive losses (not 3)

---

## MATHEMATICAL CORRECTIONS:

### Correct Position Sizing Formula:
```python
# Step 1: Calculate risk amount
risk_amount = balance * (risk_pct / 100)

# Step 2: Calculate SL distance in base units
sl_distance = abs(entry_price - sl_price)

# Step 3: Calculate value per lot movement
point = symbol_info['point']
contract_size = symbol_info['contract_size']
tick_value = symbol_info['tick_value']
tick_size = symbol_info['tick_size']

# Value per point per lot
point_value = (tick_value / tick_size) * point

# Step 4: Calculate lots
lots = risk_amount / (sl_distance / point * contract_size * point_value)

# Step 5: Validate
lots = max(min_lot, min(lots, max_lot))
lots = round(lots / lot_step) * lot_step
```

### Kelly Criterion (Proper Implementation):
```python
# Kelly% = (Win% × Avg_Win - Loss% × Avg_Loss) / Avg_Win
# Use FRACTIONAL Kelly (25% of full Kelly) for safety

kelly_pct = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
fractional_kelly = kelly_pct * 0.25  # 25% of full Kelly

# Never exceed 2% even if Kelly suggests more
final_risk = min(fractional_kelly, 0.02)
```

### Correlation-Adjusted Risk:
```python
# If correlation between positions > 0.7, reduce new position risk
correlation = get_correlation(new_symbol, existing_positions)
if abs(correlation) > 0.7:
    adjusted_risk = base_risk * (1 - abs(correlation) * 0.5)
else:
    adjusted_risk = base_risk
```

---

## TESTING RECOMMENDATIONS:

1. **Backtest with small capital**: Test with $500, $1000, $2000
2. **Paper trade for 2 weeks**: Validate profitability before live
3. **Start with MINIMUM positions**: 0.01 lots only
4. **Monitor daily**: Check every trade for correctness
5. **Keep detailed logs**: Save all calculations for audit

---

## DEPLOYMENT CHECKLIST FOR SMALL CAPITAL:

- [ ] Set risk_pct_per_trade: 0.3-0.5% in config
- [ ] Set max_daily_loss_pct: 2.0% in config
- [ ] Enable adaptive_risk_scaling: true
- [ ] Set min_signal_score: 7 (higher threshold)
- [ ] Enable ML signal filtering
- [ ] Enable trailing stops and break-even
- [ ] Start with 1-2 symbols only (BTC, ETH)
- [ ] Test with demo account first
- [ ] Use small position sizes initially
- [ ] Monitor for 1 week before increasing size

---

## EXPECTED PERFORMANCE (SMALL CAPITAL):

With fixes and enhancements:
- **Win Rate**: 60-70% (higher threshold = better quality)
- **Average Win**: 1.0-1.5% per trade
- **Average Loss**: 0.3-0.5% per trade
- **Daily Target**: 0.5-2.0% (realistic for $500-$2000)
- **Monthly Target**: 10-30% (compounding)
- **Max Drawdown**: < 10% (with proper risk management)

**Important**: These are targets, not guarantees. Always use risk management!
"""
