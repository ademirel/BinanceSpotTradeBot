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
                            close_price = order_mgr.close_position(symbol, position['quantity'])
                            
                            if close_price:
                                position_mgr.remove_position(symbol, close_price, reason)
                            else:
                                logger.error(f"Failed to close position for {symbol}")
                    
                    else:
                        if position_mgr.get_position_count() >= config.max_open_positions:
                            logger.debug(f"Skip {symbol}: Max positions ({config.max_open_positions}) reached")
                            continue
                        
                        klines = binance.get_klines(symbol, interval='1h', limit=100)
                        if not klines:
                            logger.warning(f"Skip {symbol}: Could not get klines data")
                            continue
                        
                        indicators = indicators_calc.calculate_indicators(klines)
                        if not indicators:
                            logger.warning(f"Skip {symbol}: Could not calculate indicators")
                            continue
                        
                        signal = signal_gen.generate_signal(indicators)
                        
                        if signal == 'BUY':
                            logger.info(f"BUY signal for {symbol} @ {current_price:.8f}")
                            logger.info(f"  RSI: {indicators.get('rsi', 0):.2f}, MACD: {indicators.get('macd', 0):.6f}")
                            
                            order_result = order_mgr.place_limit_buy(symbol, config.position_size_usd)
                            
                            if order_result:
                                position_mgr.add_position(
                                    symbol=order_result['symbol'],
                                    entry_price=order_result['price'],
                                    quantity=order_result['quantity'],
                                    order_id=order_result.get('order_id')
                                )
                            else:
                                logger.warning(f"Failed to place order for {symbol} - check minimum order size requirements")
                        else:
                            logger.debug(f"Skip {symbol}: No BUY signal (RSI: {indicators.get('rsi', 0):.2f}, MACD: {indicators.get('macd', 0):.6f}, Signal: {signal})")
                
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
