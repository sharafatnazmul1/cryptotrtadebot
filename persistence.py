"""
Persistence Module
Handles data storage in SQLite and CSV formats
"""

import sqlite3
import pandas as pd
import json
import csv
from datetime import datetime, timezone
from typing import Dict, List, Optional
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class Persistence:
    """
    Manages data persistence for signals, trades, and metrics
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.db_file = config['persistence']['sqlite_file']
        self.signals_csv = config['persistence']['signals_csv']
        self.trades_csv = config['persistence'].get('trades_csv', './data/trades.csv')
        
        # Create data directory if it doesn't exist
        Path(self.db_file).parent.mkdir(parents=True, exist_ok=True)
        Path(self.signals_csv).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
        
    def _init_database(self):
        """
        Initialize SQLite database with required tables
        """
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Signals table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp_utc DATETIME,
                    action_id TEXT UNIQUE,
                    strategy TEXT,
                    symbol TEXT,
                    side TEXT,
                    entry_price REAL,
                    sl_price REAL,
                    tp_price REAL,
                    atr REAL,
                    lots REAL,
                    balance_at_signal REAL,
                    htf_trend TEXT,
                    mtf_trend TEXT,
                    zone_type TEXT,
                    zone_data TEXT,
                    reason_tags TEXT,
                    signal_score INTEGER,
                    rr_ratio REAL,
                    status TEXT,
                    mt5_order_id INTEGER,
                    mt5_retcode INTEGER,
                    error TEXT,
                    notes TEXT
                )
            ''')
            
            # Trades table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp_open DATETIME,
                    timestamp_close DATETIME,
                    action_id TEXT,
                    symbol TEXT,
                    side TEXT,
                    volume REAL,
                    entry_price REAL,
                    exit_price REAL,
                    sl_price REAL,
                    tp_price REAL,
                    profit REAL,
                    commission REAL,
                    swap REAL,
                    mt5_ticket INTEGER UNIQUE,
                    mt5_magic INTEGER,
                    duration_seconds INTEGER,
                    max_profit REAL,
                    max_loss REAL,
                    notes TEXT
                )
            ''')
            
            # Metrics table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp_utc DATETIME,
                    metric_type TEXT,
                    metric_name TEXT,
                    metric_value REAL,
                    metadata TEXT
                )
            ''')
            
            # Create indices for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals(timestamp_utc)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_action_id ON signals(action_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp_open)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp_utc)')
            
            conn.commit()
            conn.close()
            
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
    

    def _make_json_safe(self, obj):
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, dict):
            return {k: self._make_json_safe(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._make_json_safe(v) for v in obj]
        return obj



    def save_signal(self, signal: Dict, status: str = 'CREATED'):
        """
        Save signal to database and CSV
        """
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Prepare data
            timestamp = signal.get('timestamp', datetime.now(timezone.utc))
            
            # Insert into database
            cursor.execute('''
                INSERT OR REPLACE INTO signals (
                    timestamp_utc, action_id, strategy, symbol, side,
                    entry_price, sl_price, tp_price, atr, lots,
                    balance_at_signal, htf_trend, mtf_trend, zone_type,
                    zone_data, reason_tags, signal_score, rr_ratio,
                    status, mt5_order_id, mt5_retcode
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now(timezone.utc).isoformat(),
                signal.get('action_id'),
                'ICT_Scalper',
                signal.get('symbol'),
                signal.get('side'),
                signal.get('entry_price'),
                signal.get('sl_price'),
                signal.get('tp_price'),
                signal.get('atr'),
                signal.get('lot_size'),
                signal.get('balance'),
                signal.get('htf_trend'),
                signal.get('mtf_trend'),
                signal.get('zone_type'),
                json.dumps(self._make_json_safe(signal.get('zone_data', {}))),
                json.dumps(self._make_json_safe(signal.get('reason_tags', []))),
                signal.get('signal_score'),
                signal.get('rr_ratio'),
                status,
                signal.get('mt5_order_id'),
                signal.get('mt5_retcode')
            ))
            
            conn.commit()
            conn.close()
            
            # Also save to CSV for easy analysis
            self._append_to_csv(self.signals_csv, signal, status)
            
            logger.debug(f"Signal saved: {signal.get('action_id')}")
            
        except Exception as e:
            logger.error(f"Error saving signal: {e}")
    
    def update_signal(self, action_id: str, **kwargs):
        """
        Update signal status and fields
        """
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Build update query dynamically
            set_clause = []
            values = []
            
            for key, value in kwargs.items():
                set_clause.append(f"{key} = ?")
                values.append(value)
            
            values.append(action_id)
            
            query = f"UPDATE signals SET {', '.join(set_clause)} WHERE action_id = ?"
            cursor.execute(query, values)
            
            conn.commit()
            conn.close()
            
            logger.debug(f"Signal updated: {action_id}")
            
        except Exception as e:
            logger.error(f"Error updating signal: {e}")
    
    def save_trade(self, trade: Dict):
        """
        Save completed trade to database
        """
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO trades (
                    timestamp_open, timestamp_close, action_id, symbol, side,
                    volume, entry_price, exit_price, sl_price, tp_price,
                    profit, commission, swap, mt5_ticket, mt5_magic,
                    duration_seconds, max_profit, max_loss
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade.get('timestamp_open'),
                trade.get('timestamp_close'),
                trade.get('action_id'),
                trade.get('symbol'),
                trade.get('side'),
                trade.get('volume'),
                trade.get('entry_price'),
                trade.get('exit_price'),
                trade.get('sl_price'),
                trade.get('tp_price'),
                trade.get('profit'),
                trade.get('commission'),
                trade.get('swap'),
                trade.get('mt5_ticket'),
                trade.get('mt5_magic'),
                trade.get('duration_seconds'),
                trade.get('max_profit'),
                trade.get('max_loss')
            ))
            
            conn.commit()
            conn.close()
            
            # Also save to CSV
            self._append_to_csv(self.trades_csv, trade)
            
            logger.info(f"Trade saved: {trade.get('mt5_ticket')}")
            
        except Exception as e:
            logger.error(f"Error saving trade: {e}")
    
    def save_metric(self, metric_type: str, metric_name: str, metric_value: float, metadata: Dict = None):
        """
        Save performance metric
        """
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO metrics (timestamp_utc, metric_type, metric_name, metric_value, metadata)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                datetime.now(timezone.utc).isoformat(),
                metric_type,
                metric_name,
                metric_value,
                json.dumps(metadata) if metadata else None
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error saving metric: {e}")
    
    def get_recent_signals(self, limit: int = 10) -> List[Dict]:
        """
        Get recent signals from database
        """
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM signals
                ORDER BY timestamp_utc DESC
                LIMIT ?
            ''', (limit,))
            
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            
            conn.close()
            
            signals = []
            for row in rows:
                signal = dict(zip(columns, row))
                # Parse JSON fields
                if signal.get('zone_data'):
                    signal['zone_data'] = json.loads(signal['zone_data'])
                if signal.get('reason_tags'):
                    signal['reason_tags'] = json.loads(signal['reason_tags'])
                signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error getting recent signals: {e}")
            return []
    
    def get_recent_trades(self, limit: int = 10) -> List[Dict]:
        """
        Get recent completed trades
        """
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM trades
                ORDER BY timestamp_close DESC
                LIMIT ?
            ''', (limit,))
            
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            
            conn.close()
            
            trades = []
            for row in rows:
                trade = dict(zip(columns, row))
                trades.append(trade)
            
            return trades
            
        except Exception as e:
            logger.error(f"Error getting recent trades: {e}")
            return []
    
    def get_performance_stats(self, days: int = 30) -> Dict:
        """
        Calculate performance statistics
        """
        try:
            conn = sqlite3.connect(self.db_file)
            
            # Get trades from last N days
            query = '''
                SELECT * FROM trades
                WHERE timestamp_close >= datetime('now', '-{} days')
                ORDER BY timestamp_close
            '''.format(days)
            
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if df.empty:
                return {}
            
            # Calculate statistics
            total_trades = len(df)
            winning_trades = len(df[df['profit'] > 0])
            losing_trades = len(df[df['profit'] < 0])
            
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            
            avg_win = df[df['profit'] > 0]['profit'].mean() if winning_trades > 0 else 0
            avg_loss = df[df['profit'] < 0]['profit'].mean() if losing_trades > 0 else 0
            
            total_profit = df['profit'].sum()
            total_commission = df['commission'].sum() if 'commission' in df else 0
            total_swap = df['swap'].sum() if 'swap' in df else 0
            net_profit = total_profit - total_commission - total_swap
            
            # Calculate max drawdown
            cumulative = df['profit'].cumsum()
            running_max = cumulative.cummax()
            drawdown = cumulative - running_max
            max_drawdown = drawdown.min()
            
            # Calculate profit factor
            gross_profit = df[df['profit'] > 0]['profit'].sum() if winning_trades > 0 else 0
            gross_loss = abs(df[df['profit'] < 0]['profit'].sum()) if losing_trades > 0 else 1
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
            
            # Calculate average trade duration
            if 'duration_seconds' in df:
                avg_duration = df['duration_seconds'].mean() / 3600  # Convert to hours
            else:
                avg_duration = 0
            
            stats = {
                'period_days': days,
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': win_rate,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'total_profit': total_profit,
                'total_commission': total_commission,
                'total_swap': total_swap,
                'net_profit': net_profit,
                'max_drawdown': max_drawdown,
                'profit_factor': profit_factor,
                'avg_trade_duration_hours': avg_duration,
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error calculating performance stats: {e}")
            return {}
    
    def _append_to_csv(self, filename: str, data: Dict, status: str = None):
        """
        Append data to CSV file
        """
        try:
            # Check if file exists
            file_exists = Path(filename).exists()
            
            # Prepare row
            row = data.copy()
            if status:
                row['status'] = status
            row['timestamp'] = datetime.now(timezone.utc).isoformat()
            row = self._make_json_safe(row)

            
            # Convert complex types to strings
            for key, value in row.items():
                if isinstance(value, (dict, list)):
                    row[key] = json.dumps(value)
            
            # Write to CSV
            with open(filename, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=row.keys())
                
                if not file_exists:
                    writer.writeheader()
                
                writer.writerow(row)
            
        except Exception as e:
            logger.error(f"Error writing to CSV: {e}")
    
    def backup_database(self):
        """
        Create backup of database
        """
        try:
            import shutil
            from datetime import datetime
            
            backup_dir = Path(self.db_file).parent / 'backups'
            backup_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = backup_dir / f"ledger_backup_{timestamp}.sqlite"
            
            shutil.copy2(self.db_file, backup_file)
            
            logger.info(f"Database backed up to {backup_file}")
            
            # Keep only last 7 backups
            backups = sorted(backup_dir.glob("ledger_backup_*.sqlite"))
            if len(backups) > 7:
                for old_backup in backups[:-7]:
                    old_backup.unlink()
            
        except Exception as e:
            logger.error(f"Error backing up database: {e}")
