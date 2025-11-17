"""
Backtest Runner Script
Easy-to-use script for running backtests
"""

import sys
import os
import logging
import yaml
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import MetaTrader5 as mt5

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backtest_engine import BacktestEngine
from backtest_analytics import BacktestAnalytics


def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    log_level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(f'./logs/backtest_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        ]
    )

    # Suppress some noisy loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)


def load_config(config_file: str) -> dict:
    """Load configuration file"""
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        print(f"Error loading config: {e}")
        sys.exit(1)


def initialize_mt5(config: dict) -> bool:
    """Initialize MT5 connection"""
    try:
        # Get credentials
        login = os.getenv('MT5_LOGIN') or config.get('mt5', {}).get('login')
        password = os.getenv('MT5_PASSWORD') or config.get('mt5', {}).get('password')
        server = os.getenv('MT5_SERVER') or config.get('mt5', {}).get('server')
        path = os.getenv('MT5_PATH') or config.get('mt5', {}).get('path')

        if not all([login, password, server]):
            print("Error: MT5 credentials not configured")
            return False

        # Initialize
        init_params = {}
        if path:
            init_params['path'] = path

        if not mt5.initialize(**init_params):
            print(f"MT5 initialization failed: {mt5.last_error()}")
            return False

        # Login
        if not mt5.login(int(login), password=password, server=server):
            print(f"MT5 login failed: {mt5.last_error()}")
            mt5.shutdown()
            return False

        print(f"MT5 connected successfully ({server})")
        return True

    except Exception as e:
        print(f"Error initializing MT5: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Run backtest for trading bot')
    parser.add_argument('--config', type=str, default='config_small_capital.yaml',
                       help='Configuration file (default: config_small_capital.yaml)')
    parser.add_argument('--start-date', type=str, required=True,
                       help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, required=True,
                       help='End date (YYYY-MM-DD)')
    parser.add_argument('--balance', type=float, default=1000,
                       help='Initial balance (default: 1000)')
    parser.add_argument('--no-cache', action='store_true',
                       help='Do not use cached data')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose logging')
    parser.add_argument('--output-dir', type=str, default='./backtest_results',
                       help='Output directory for results (default: ./backtest_results)')

    args = parser.parse_args()

    # Create logs directory
    Path('./logs').mkdir(exist_ok=True)

    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    try:
        print("="*80)
        print("TRADING BOT - BACKTEST RUNNER")
        print("="*80)
        print()

        # Load configuration
        print(f"Loading configuration: {args.config}")
        config = load_config(args.config)

        # Initialize MT5 (optional for backtest - will use defaults if not available)
        print("Initializing MT5 connection (optional for backtest)...")
        mt5_initialized = initialize_mt5(config)
        if not mt5_initialized:
            print("MT5 not available - using default symbol specifications")
            print("Note: For best accuracy, configure MT5 credentials to fetch real symbol info")

        # Parse dates
        try:
            start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
            end_date = datetime.strptime(args.end_date, '%Y-%m-%d')

            # Add timezone info
            from datetime import timezone as tz
            start_date = start_date.replace(tzinfo=tz.utc)
            end_date = end_date.replace(tzinfo=tz.utc)

        except ValueError as e:
            print(f"Invalid date format: {e}")
            print("Use format: YYYY-MM-DD")
            sys.exit(1)

        # Validate dates
        if start_date >= end_date:
            print("Error: Start date must be before end date")
            sys.exit(1)

        current_date = datetime.now(tz.utc)
        if start_date > current_date:
            print(f"Error: Start date {start_date.date()} is in the future")
            print(f"Current date: {current_date.date()}")
            sys.exit(1)

        if end_date > current_date:
            print(f"Error: End date {end_date.date()} is in the future")
            print(f"Current date: {current_date.date()}")
            print("You can only backtest historical data, not future dates")
            sys.exit(1)

        duration = (end_date - start_date).days
        if duration < 7:
            print("Warning: Backtest period is very short (less than 7 days)")
            print("Results may not be statistically significant.")
            print()

        # Print backtest info
        print()
        print("BACKTEST CONFIGURATION:")
        print("-"*80)
        print(f"Symbol: {config['symbol']}")
        print(f"Period: {start_date.date()} to {end_date.date()} ({duration} days)")
        print(f"Initial Balance: ${args.balance:,.2f}")
        print(f"Timeframes: HTF={config['timeframes']['high']}, "
              f"MTF={config['timeframes']['med']}, LTF={config['timeframes']['low']}")
        print(f"Use Cache: {not args.no_cache}")
        print("-"*80)
        print()

        # Ask for confirmation
        response = input("Proceed with backtest? (y/n): ")
        if response.lower() != 'y':
            print("Backtest cancelled.")
            sys.exit(0)

        print()
        print("Starting backtest...")
        print()

        # Create backtest engine
        engine = BacktestEngine(
            config=config,
            start_date=start_date,
            end_date=end_date,
            initial_balance=args.balance
        )

        # Progress callback
        def progress_callback(progress, current_time):
            if int(progress) % 10 == 0:  # Update every 10%
                print(f"Progress: {progress:.1f}% - {current_time.date()}")

        # Run backtest
        results = engine.run(use_cache=not args.no_cache, progress_callback=progress_callback)

        if not results:
            print()
            print("Backtest failed. Check logs for details.")
            sys.exit(1)

        # Generate analytics
        print()
        print("Generating analytics...")
        analytics = BacktestAnalytics(results)

        # Create output directory
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate timestamp for files
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Generate and print report
        report = analytics.generate_report(
            save_path=output_dir / f'report_{timestamp}.txt'
        )

        print()
        print(report)

        # Save additional files
        print()
        print("Saving results...")
        analytics.save_results_json(output_dir / f'results_{timestamp}.json')
        analytics.save_equity_curve_csv(output_dir / f'equity_curve_{timestamp}.csv')
        analytics.save_trades_csv(output_dir / f'trades_{timestamp}.csv')

        print()
        print(f"All results saved to: {output_dir}")
        print()
        print("="*80)
        print("BACKTEST COMPLETED SUCCESSFULLY")
        print("="*80)

    except KeyboardInterrupt:
        print()
        print("Backtest interrupted by user.")
        sys.exit(1)

    except Exception as e:
        logger.error(f"Backtest error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        # Cleanup
        try:
            mt5.shutdown()
        except:
            pass


if __name__ == "__main__":
    main()
