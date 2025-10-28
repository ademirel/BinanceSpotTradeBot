#!/usr/bin/env python3
import time
import sys
from src.logger import setup_logger
from src.config_loader import ConfigLoader
from src.binance_client import BinanceClientWrapper
from src.indicators import TechnicalIndicators
from src.signal_generator import SignalGenerator
from src.position_manager import PositionManager
from src.order_manager import OrderManager
from src.pair_scanner import PairScanner

def main():
    logger = setup_logger()
    logger.info("=" * 70)
    logger.info("Binance Spot Trading Bot - EMA/RSI/Heiken Ashi Strategy")
    logger.info("=" * 70)
    
    try:
        config = ConfigLoader()
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        logger.error("Please make sure config.yaml exists and .env file contains API keys")
        sys.exit(1)
    
    if not config.api_key or not config.api_secret:
        logger.error("BINANCE_API_KEY and BINANCE_API_SECRET must be set in .env file")
        logger.error("Copy .env.example to .env and add your API keys")
        sys.exit(1)
    
    # Initialize components
    binance = BinanceClientWrapper(
        api_key=config.api_key,
        api_secret=config.api_secret,
        testnet=config.testnet,
        logger=logger
    )
    
    indicators_calc = TechnicalIndicators(config, logger)
    signal_gen = SignalGenerator(config, logger)
    position_mgr = PositionManager(config, logger)
    order_mgr = OrderManager(binance, config, logger)
    pair_scanner = PairScanner(binance, indicators_calc, config, logger)
    
    # Display configuration
    logger.info(f"\nStrategy Configuration:")
    logger.info(f"  Indicators:")
    logger.info(f"    - EMA Fast: {config.get('indicators.ema.fast', 21)}")
    logger.info(f"    - EMA Slow: {config.get('indicators.ema.slow', 49)}")
    logger.info(f"    - RSI Period: {config.get('indicators.rsi.period', 14)}")
    logger.info(f"    - RSI Oversold: <{config.get('indicators.rsi.oversold', 10)}")
    logger.info(f"    - RSI Overbought: >{config.get('indicators.rsi.overbought', 90)}")
    logger.info(f"    - ATR Period: {config.get('indicators.atr.period', 14)}")
    
    logger.info(f"\n  Risk Management:")
    logger.info(f"    - Max Positions: {config.get('risk_management.max_positions', 5)}")
    logger.info(f"    - Position Size: {config.get('risk_management.position_size_percent', 25)}% of portfolio")
    logger.info(f"    - Daily Loss Limit: {config.get('risk_management.daily_loss_limit_percent', 3)}%")
    logger.info(f"    - Profit Protection: {config.get('risk_management.daily_profit_protection_percent', 3)}%")
    
    logger.info(f"\n  Exit Strategy:")
    logger.info(f"    - Initial Trailing Stop: {config.get('exit.trailing_stop.initial_percent', 2.5)}%")
    logger.info(f"    - ATR Multiplier: {config.get('exit.trailing_stop.atr_multiplier', 2.0)}×")
    logger.info(f"    - RSI Reversal: {'Enabled' if config.get('exit.use_rsi_reversal', True) else 'Disabled'}")
    logger.info(f"    - EMA Re-cross: {'Enabled' if config.get('exit.use_ema_recross', True) else 'Disabled'}")
    
    logger.info(f"\n  Scanner:")
    scanner_pairs = config.get('scanner.pairs', [])
    logger.info(f"    - Pairs to scan: {len(scanner_pairs)}")
    logger.info(f"    - Scan interval: {config.get('scanner.scan_interval_seconds', 60)}s")
    logger.info(f"    - Volatility filter: ATR > {config.get('volatility.atr_multiplier', 1.5)}× avg")
    
    # Get account balance
    usdt_balance = binance.get_account_balance('USDT')
    logger.info(f"\nUSDT Balance: ${usdt_balance:.2f}")
    
    # Check daily P&L status
    daily_pnl = position_mgr.get_daily_pnl()
    logger.info(f"Daily P&L: {daily_pnl.get('total_pnl', 0):.2f}% ({daily_pnl.get('trades_count', 0)} trades)")
    
    iteration = 0
    
    logger.info("\n" + "=" * 70)
    logger.info("Starting trading loop...")
    logger.info("Press Ctrl+C to stop the bot")
    logger.info("=" * 70 + "\n")
    
    try:
        while True:
            iteration += 1
            logger.info(f"\n{'='*70}")
            logger.info(f"Iteration #{iteration} - {time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"{'='*70}")
            
            # Check daily P&L and protection modes
            daily_pnl = position_mgr.get_daily_pnl()
            logger.info(f"Daily P&L: {daily_pnl.get('total_pnl', 0):.2f}% | Trades: {daily_pnl.get('trades_count', 0)} (W: {daily_pnl.get('wins', 0)}, L: {daily_pnl.get('losses', 0)})")
            
            if position_mgr.is_in_protection_mode():
                logger.warning(f"⚠️  PROFIT PROTECTION MODE ACTIVE - No new trades (Daily profit: {daily_pnl.get('total_pnl', 0):.2f}%)")
            
            if position_mgr.has_hit_daily_loss_limit():
                logger.error(f"🛑 DAILY LOSS LIMIT HIT - No new trades (Daily loss: {daily_pnl.get('total_pnl', 0):.2f}%)")
            
            # Scan pairs for opportunities
            if iteration % 5 == 1:  # Rescan every 5 iterations
                logger.info("\n🔍 Scanning pairs for trading opportunities...")
                pair_scanner.scan_pairs(force_scan=True)
            
            # Get current account balance
            usdt_balance = binance.get_account_balance('USDT')
            
            # Get open positions
            open_positions = position_mgr.get_open_positions()
            logger.info(f"\nOpen Positions: {len(open_positions)}/{config.get('risk_management.max_positions', 5)}")
            logger.info(f"USDT Balance: ${usdt_balance:.2f}")
            
            # 1. Manage existing positions
            for symbol, position in list(open_positions.items()):
                try:
                    current_price = binance.get_symbol_price(symbol)
                    if not current_price:
                        logger.warning(f"Skip {symbol}: Could not get price")
                        continue
                    
                    # Get fresh indicators
                    timeframe = config.get('timeframe', '15m')
                    klines = binance.get_klines(symbol, interval=timeframe, limit=100)
                    
                    if klines:
                        indicators = indicators_calc.calculate_indicators(klines)
                        
                        if indicators:
                            # Update trailing stop with ATR
                            atr_value = indicators_calc.get_atr_for_trailing_stop(klines)
                            position_mgr.update_trailing_stop(symbol, current_price, atr_value)
                            
                            # Check exit signals (RSI reversal, EMA recross)
                            exit_check = signal_gen.check_exit_signal(position, indicators)
                            
                            if exit_check.get('should_exit'):
                                logger.info(f"📉 Exit signal for {symbol}: {exit_check.get('reason')}")
                                
                                close_result = order_mgr.close_position(symbol, position['quantity'])
                                
                                if isinstance(close_result, str):
                                    if close_result in ['PHANTOM_POSITION', 'BELOW_MIN_QTY', 'ZERO_QUANTITY']:
                                        logger.error(f"Position closure failed: {close_result} - Removing phantom")
                                        position_mgr.remove_position(symbol, current_price, f"{exit_check.get('reason')}_PHANTOM")
                                elif close_result:
                                    position_mgr.remove_position(symbol, close_result, exit_check.get('reason'))
                                else:
                                    logger.error(f"Failed to close {symbol} - will retry")
                                continue
                    
                    # Check stop loss and trailing stop
                    should_close, reason = position_mgr.should_close_position(symbol, current_price)
                    
                    if should_close:
                        logger.info(f"🛑 Stop triggered for {symbol}: {reason}")
                        
                        close_result = order_mgr.close_position(symbol, position['quantity'])
                        
                        if isinstance(close_result, str):
                            if close_result in ['PHANTOM_POSITION', 'BELOW_MIN_QTY', 'ZERO_QUANTITY']:
                                logger.error(f"Position closure failed: {close_result} - Removing phantom")
                                position_mgr.remove_position(symbol, current_price, f"{reason}_PHANTOM")
                        elif close_result:
                            position_mgr.remove_position(symbol, close_result, reason)
                        else:
                            logger.error(f"Failed to close {symbol} - will retry")
                
                except Exception as e:
                    logger.error(f"Error managing position {symbol}: {e}")
                    continue
            
            # 2. Look for new entry opportunities
            if not position_mgr.is_in_protection_mode() and not position_mgr.has_hit_daily_loss_limit():
                # Get top pairs from scanner
                top_pairs = pair_scanner.get_top_pairs()
                
                for pair_data in top_pairs:
                    symbol = pair_data['symbol']
                    
                    try:
                        # Skip if already have position
                        if position_mgr.has_position(symbol):
                            continue
                        
                        # Check if can open new position
                        can_open, reason = position_mgr.can_open_new_position(symbol)
                        if not can_open:
                            logger.debug(f"Skip {symbol}: {reason}")
                            continue
                        
                        # Get fresh data
                        current_price = binance.get_symbol_price(symbol)
                        if not current_price:
                            continue
                        
                        timeframe = config.get('timeframe', '15m')
                        klines = binance.get_klines(symbol, interval=timeframe, limit=100)
                        
                        if not klines:
                            continue
                        
                        # Calculate indicators
                        indicators = indicators_calc.calculate_indicators(klines)
                        
                        if not indicators:
                            continue
                        
                        # Generate entry signal
                        signal = signal_gen.generate_entry_signal(indicators)
                        
                        if signal in ['BUY', 'SELL']:
                            # Log signal details
                            logger.info(f"\n{'🟢 BUY' if signal == 'BUY' else '🔴 SELL'} signal for {symbol} @ {current_price:.8f}")
                            logger.info(f"  EMA Fast (21): {indicators.get('ema_fast', 0):.8f}")
                            logger.info(f"  EMA Slow (49): {indicators.get('ema_slow', 0):.8f}")
                            logger.info(f"  RSI: {indicators.get('rsi', 0):.2f}")
                            logger.info(f"  EMA Crossover: {indicators.get('ema_crossover_up' if signal == 'BUY' else 'ema_crossover_down', False)}")
                            logger.info(f"  Heiken Ashi: {'Bullish' if indicators.get('ha_bullish') else 'Bearish' if indicators.get('ha_bearish') else 'Neutral'}")
                            logger.info(f"  ATR: {indicators.get('atr', 0):.8f}")
                            logger.info(f"  Volatility Filter: {'✓ PASS' if indicators.get('passes_volatility_filter') else '✗ FAIL'}")
                            
                            # Calculate position size
                            quantity, position_value_usd = position_mgr.calculate_position_size(current_price, usdt_balance)
                            
                            logger.info(f"  Position Size: ${position_value_usd:.2f} ({position_mgr.position_size_percent}% of ${usdt_balance:.2f})")
                            logger.info(f"  Quantity: {quantity:.8f}")
                            
                            # Place market order
                            if signal == 'BUY':
                                order_result = order_mgr.place_market_buy(symbol, position_value_usd)
                            else:
                                # For SELL signals, we would need to short (not implemented for spot)
                                logger.info(f"  SELL signal detected but shorting not available on spot - skipping")
                                continue
                            
                            if order_result:
                                executed_qty = order_result.get('quantity', 0)
                                
                                if executed_qty > 0:
                                    logger.info(f"✓ Order executed: {symbol} {signal} - Qty: {executed_qty}, Price: {order_result['price']:.8f}")
                                    
                                    try:
                                        position_mgr.add_position(
                                            symbol=order_result['symbol'],
                                            entry_price=order_result['price'],
                                            quantity=executed_qty,
                                            side=signal,
                                            order_id=order_result.get('order_id')
                                        )
                                        logger.info(f"✓ Position {symbol} saved successfully")
                                        
                                        # Update balance
                                        usdt_balance = binance.get_account_balance('USDT')
                                        
                                    except Exception as save_error:
                                        logger.error(f"✗ CRITICAL: Position save failed for {symbol}!")
                                        logger.error(f"✗ Order executed on Binance but NOT saved!")
                                        logger.error(f"✗ Manual intervention required!")
                                        logger.error(f"✗ Error: {save_error}")
                                else:
                                    logger.error(f"✗ PREVENTED phantom position: {symbol} executedQty=0")
                            else:
                                logger.warning(f"Failed to place order for {symbol}")
                        
                        else:
                            logger.debug(f"Skip {symbol}: Signal={signal}")
                    
                    except Exception as e:
                        logger.error(f"Error processing {symbol}: {e}")
                        continue
            
            # Sleep before next iteration
            check_interval = config.get('bot.check_interval_seconds', 60)
            logger.info(f"\n⏱️  Waiting {check_interval}s until next check...")
            time.sleep(check_interval)
    
    except KeyboardInterrupt:
        logger.info("\n" + "="*70)
        logger.info("Bot stopped by user")
        logger.info("="*70)
        
        # Display final status
        open_positions = position_mgr.get_open_positions()
        daily_pnl = position_mgr.get_daily_pnl()
        
        logger.info(f"\nFinal Status:")
        logger.info(f"  Daily P&L: {daily_pnl.get('total_pnl', 0):.2f}%")
        logger.info(f"  Total Trades: {daily_pnl.get('trades_count', 0)}")
        logger.info(f"  Wins: {daily_pnl.get('wins', 0)} | Losses: {daily_pnl.get('losses', 0)}")
        
        if open_positions:
            logger.info(f"\n  Open Positions: {len(open_positions)}")
            for symbol, pos in open_positions.items():
                current_price = binance.get_symbol_price(symbol)
                if current_price:
                    side = pos.get('side', 'BUY')
                    if side == 'BUY':
                        pnl = ((current_price - pos['entry_price']) / pos['entry_price']) * 100
                    else:
                        pnl = ((pos['entry_price'] - current_price) / pos['entry_price']) * 100
                    
                    logger.info(f"    {symbol} {side}: Entry: {pos['entry_price']:.8f}, Current: {current_price:.8f}, P/L: {pnl:.2f}%")
        else:
            logger.info(f"\n  No open positions")
        
        logger.info("\nBot shutdown complete")
    
    except Exception as e:
        logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
