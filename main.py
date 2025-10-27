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

def main():
    logger = setup_logger()
    logger.info("=" * 60)
    logger.info("Binance Trading Bot Started")
    logger.info("=" * 60)
    
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
    
    logger.info(f"Configuration loaded:")
    logger.info(f"  - Top coins: {config.top_coins_count}")
    logger.info(f"  - Position size: ${config.position_size_usd}")
    logger.info(f"  - Stop loss: {config.stop_loss_percent}%")
    logger.info(f"  - Trailing stop: {config.trailing_stop_percent}%")
    logger.info(f"  - Check interval: {config.check_interval}s")
    logger.info(f"  - Max open positions: {config.max_open_positions}")
    
    usdt_balance = binance.get_account_balance('USDT')
    logger.info(f"USDT Balance: ${usdt_balance:.2f}")
    
    top_coins = []
    iteration = 0
    
    logger.info("\nStarting trading loop...")
    logger.info("Press Ctrl+C to stop the bot\n")
    
    try:
        while True:
            iteration += 1
            logger.info(f"\n{'='*60}")
            logger.info(f"Iteration #{iteration} - {time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"{'='*60}")
            
            if iteration % 10 == 1:
                logger.info("Refreshing top coins list...")
                top_coins = binance.get_top_volume_pairs(config.top_coins_count)
                
                if not top_coins:
                    logger.error("Failed to get top coins, retrying in next iteration")
                    time.sleep(config.check_interval)
                    continue
                else:
                    logger.info(f"Top {len(top_coins)} coins by volume: {', '.join(top_coins)}")
            
            open_positions = position_mgr.get_open_positions()
            logger.info(f"Open positions: {len(open_positions)}/{config.max_open_positions}")
            
            for symbol in top_coins:
                try:
                    current_price = binance.get_symbol_price(symbol)
                    if not current_price:
                        logger.warning(f"Skip {symbol}: Could not get current price")
                        continue
                    
                    if position_mgr.has_position(symbol):
                        position_mgr.update_position(symbol, current_price)
                        
                        should_close, reason = position_mgr.should_close_position(symbol, current_price)
                        
                        if should_close:
                            position = position_mgr.get_open_positions()[symbol]
                            close_result = order_mgr.close_position(symbol, position['quantity'])
                            
                            if isinstance(close_result, str):
                                if close_result in ['PHANTOM_POSITION', 'BELOW_MIN_QTY', 'ZERO_QUANTITY']:
                                    logger.error(f"Position closure failed for {symbol}: {close_result} - Removing phantom position")
                                    position_mgr.remove_position(symbol, current_price, f"{reason}_PHANTOM")
                                else:
                                    logger.error(f"Unknown error closing {symbol}: {close_result}")
                            elif close_result:
                                position_mgr.remove_position(symbol, close_result, reason)
                            else:
                                logger.error(f"Failed to close position for {symbol} - will retry next iteration")
                    
                    else:
                        if position_mgr.get_position_count() >= config.max_open_positions:
                            logger.debug(f"Skip {symbol}: Max positions ({config.max_open_positions}) reached")
                            continue
                        
                        timeframe = str(config.get('timeframe', '15m'))
                        klines_15m = binance.get_klines(symbol, interval=timeframe, limit=100)
                        if not klines_15m:
                            logger.warning(f"Skip {symbol}: Could not get 15m klines data")
                            continue
                        
                        klines_1d = binance.get_klines(symbol, interval='1d', limit=10)
                        if not klines_1d:
                            logger.warning(f"Skip {symbol}: Could not get daily klines data")
                            continue
                        
                        indicators = indicators_calc.calculate_indicators(klines_15m)
                        if not indicators:
                            logger.warning(f"Skip {symbol}: Could not calculate indicators")
                            continue
                        
                        signal = signal_gen.generate_signal(indicators)
                        
                        if signal == 'BUY':
                            ma_fast = indicators.get('ma_fast')
                            ma_medium = indicators.get('ma_medium')
                            ma_slow = indicators.get('ma_slow')
                            ma_fast_crossed = indicators.get('ma_fast_crossed_slow', False)
                            ma_medium_crossed = indicators.get('ma_medium_crossed_slow', False)
                            
                            ma_fast_str = f"{ma_fast:.8f}" if ma_fast is not None else "N/A"
                            ma_medium_str = f"{ma_medium:.8f}" if ma_medium is not None else "N/A"
                            ma_slow_str = f"{ma_slow:.8f}" if ma_slow is not None else "N/A"
                            
                            logger.info(f"BUY signal for {symbol} @ {current_price:.8f}")
                            logger.info(f"  MA 9: {ma_fast_str}")
                            logger.info(f"  MA 21: {ma_medium_str}")
                            logger.info(f"  MA 49: {ma_slow_str}")
                            logger.info(f"  MA9 crossed MA49: {ma_fast_crossed}")
                            logger.info(f"  MA21 crossed MA49: {ma_medium_crossed}")
                            
                            pivot_check = indicators_calc.check_daily_pivot_test(klines_15m, klines_1d, current_price)
                            
                            if not pivot_check['valid_entry']:
                                pivot_level_str = f"{pivot_check['pivot_level']:.8f}" if pivot_check['pivot_level'] else "N/A"
                                if not pivot_check['tested']:
                                    logger.info(f"✗ SKIP {symbol}: Price has not tested daily pivot yet")
                                elif pivot_check['broken']:
                                    logger.info(f"✗ SKIP {symbol}: Daily pivot broken (price below pivot)")
                                logger.info(f"  Daily Pivot Level: {pivot_level_str}")
                                continue
                            
                            logger.info(f"✓ Daily Pivot validated: tested but not broken")
                            logger.info(f"  Daily Pivot Level: {pivot_check['pivot_level']:.8f}")
                            
                            order_result = order_mgr.place_limit_buy(symbol, config.position_size_usd)
                            
                            if order_result:
                                executed_qty = order_result.get('quantity', 0)
                                if executed_qty > 0:
                                    logger.info(f"✓ Adding position: {symbol} - Qty: {executed_qty}, Price: {order_result['price']}")
                                    try:
                                        position_mgr.add_position(
                                            symbol=order_result['symbol'],
                                            entry_price=order_result['price'],
                                            quantity=executed_qty,
                                            order_id=order_result.get('order_id')
                                        )
                                        logger.info(f"✓ Position {symbol} successfully saved to positions.json")
                                    except Exception as save_error:
                                        logger.error(f"✗ CRITICAL: Position save failed for {symbol}!")
                                        logger.error(f"✗ Order was executed on Binance but NOT saved to positions.json!")
                                        logger.error(f"✗ Manual intervention required - Check Binance orders!")
                                        logger.error(f"✗ Error: {save_error}")
                                else:
                                    logger.error(f"✗ PREVENTED phantom position: {symbol} returned executedQty=0")
                            else:
                                logger.warning(f"Failed to place order for {symbol} - check minimum order size requirements")
                        else:
                            logger.debug(f"Skip {symbol}: Signal={signal}")
                
                except Exception as e:
                    logger.error(f"Error processing {symbol}: {e}")
                    continue
            
            logger.info(f"\nWaiting {config.check_interval} seconds until next check...")
            time.sleep(config.check_interval)
    
    except KeyboardInterrupt:
        logger.info("\n" + "="*60)
        logger.info("Bot stopped by user")
        logger.info("="*60)
        
        open_positions = position_mgr.get_open_positions()
        if open_positions:
            logger.info(f"\nYou have {len(open_positions)} open positions:")
            for symbol, pos in open_positions.items():
                current_price = binance.get_symbol_price(symbol)
                if current_price:
                    pnl = ((current_price - pos['entry_price']) / pos['entry_price']) * 100
                    logger.info(f"  {symbol}: Entry: {pos['entry_price']:.8f}, Current: {current_price:.8f}, P/L: {pnl:.2f}%")
        
        logger.info("\nBot shutdown complete")
    
    except Exception as e:
        logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
