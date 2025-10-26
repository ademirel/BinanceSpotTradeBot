# Binance Trading Bot - Project Information

## Overview
Automated trading bot for Binance spot market that trades the top 20 coins by volume using momentum-based strategy with trailing stop mechanism.

## Project Architecture

### Core Components
1. **main.py**: Main bot loop - coordinates all modules
2. **src/logger.py**: Logging system setup
3. **src/config_loader.py**: Configuration and environment management
4. **src/binance_client.py**: Binance API wrapper
5. **src/indicators.py**: Technical indicators calculation (RSI, MACD, MA)
6. **src/signal_generator.py**: Trading signal generation logic
7. **src/position_manager.py**: Position tracking and management
8. **src/order_manager.py**: Order execution and quantity calculations

### Strategy
- Automatically selects top 20 coins by 24h volume
- Uses RSI, MACD, and Moving Averages for signal generation
- Places limit buy orders (0.2% below market price)
- Implements stop-loss (2%) and trailing stop (1.5%) for risk management
- Trades $100 (configurable) per position

### Configuration
- **config.yaml**: Trading parameters (coin count, position size, stop-loss, etc.)
- **.env**: API credentials (not tracked in git)

### Data Storage
- **logs/**: Daily trading logs and trade history
- **positions.json**: Current open positions (persists across restarts)

## Recent Changes
- 2025-10-26: Initial project setup
  - Installed Python 3.12 and dependencies
  - Created modular bot architecture
  - Implemented multi-pair trading support
  - Added comprehensive logging system
  - Created README and documentation

## Dependencies
- python-binance: Binance API client
- pandas & numpy: Data analysis
- pandas-ta: Technical indicators
- python-dotenv: Environment variables
- pyyaml: Configuration file parsing

## User Preferences
- No dashboard/UI - log file based monitoring only
- Python-only implementation
- Top 20 coins by volume
- $100 per position (configurable via config.yaml)
