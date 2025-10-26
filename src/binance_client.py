from binance.client import Client
from binance.exceptions import BinanceAPIException
import time

class BinanceClientWrapper:
    def __init__(self, api_key, api_secret, testnet=False, logger=None):
        self.logger = logger
        self.client = Client(api_key, api_secret, testnet=testnet)
        if self.logger:
            self.logger.info(f"Binance client initialized (Testnet: {testnet})")
    
    def get_top_volume_pairs(self, top_n=20, quote_asset='USDT'):
        try:
            tickers = self.client.get_ticker()
            
            usdt_pairs = [
                ticker for ticker in tickers 
                if ticker['symbol'].endswith(quote_asset) and 
                not any(x in ticker['symbol'] for x in ['UP', 'DOWN', 'BEAR', 'BULL'])
            ]
            
            for ticker in usdt_pairs:
                ticker['quoteVolume'] = float(ticker['quoteVolume'])
            
            sorted_pairs = sorted(usdt_pairs, key=lambda x: x['quoteVolume'], reverse=True)
            
            top_pairs = [pair['symbol'] for pair in sorted_pairs[:top_n]]
            
            if self.logger:
                self.logger.info(f"Top {top_n} pairs by volume: {', '.join(top_pairs)}")
            
            return top_pairs
            
        except BinanceAPIException as e:
            if self.logger:
                self.logger.error(f"Error fetching top volume pairs: {e}")
            return []
    
    def get_symbol_price(self, symbol):
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error getting price for {symbol}: {e}")
            return None
    
    def get_klines(self, symbol, interval='1h', limit=100):
        try:
            klines = self.client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            return klines
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error getting klines for {symbol}: {e}")
            return []
    
    def get_account_balance(self, asset='USDT'):
        try:
            balance = self.client.get_asset_balance(asset=asset)
            return float(balance['free']) if balance else 0.0
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error getting balance for {asset}: {e}")
            return 0.0
    
    def create_limit_buy_order(self, symbol, quantity, price):
        try:
            order = self.client.order_limit_buy(
                symbol=symbol,
                quantity=quantity,
                price=price
            )
            if self.logger:
                self.logger.info(f"Limit buy order created for {symbol}: {quantity} @ {price}")
            return order
        except BinanceAPIException as e:
            if self.logger:
                self.logger.error(f"Error creating buy order for {symbol}: {e}")
            return None
    
    def get_order_status(self, symbol, order_id):
        try:
            order = self.client.get_order(symbol=symbol, orderId=order_id)
            return order
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error getting order status for {symbol}: {e}")
            return None
    
    def cancel_order(self, symbol, order_id):
        try:
            result = self.client.cancel_order(symbol=symbol, orderId=order_id)
            if self.logger:
                self.logger.info(f"Order {order_id} cancelled for {symbol}")
            return result
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error cancelling order {order_id} for {symbol}: {e}")
            return None
    
    def create_limit_sell_order(self, symbol, quantity, price):
        try:
            order = self.client.order_limit_sell(
                symbol=symbol,
                quantity=quantity,
                price=price
            )
            if self.logger:
                self.logger.info(f"Limit sell order created for {symbol}: {quantity} @ {price}")
            return order
        except BinanceAPIException as e:
            if self.logger:
                self.logger.error(f"Error creating sell order for {symbol}: {e}")
            return None
    
    def create_market_sell_order(self, symbol, quantity):
        try:
            order = self.client.order_market_sell(
                symbol=symbol,
                quantity=quantity
            )
            if self.logger:
                self.logger.info(f"Market sell order created for {symbol}: {quantity}")
            return order
        except BinanceAPIException as e:
            if self.logger:
                self.logger.error(f"Error creating market sell order for {symbol}: {e}")
            return None
    
    def get_symbol_info(self, symbol):
        try:
            info = self.client.get_symbol_info(symbol)
            return info
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error getting symbol info for {symbol}: {e}")
            return None
    
    def get_asset_balance_quantity(self, asset):
        try:
            balance = self.client.get_asset_balance(asset=asset)
            return float(balance['free']) if balance else 0.0
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error getting balance quantity for {asset}: {e}")
            return 0.0
    
    def get_my_trades(self, symbol, limit=10):
        try:
            trades = self.client.get_my_trades(symbol=symbol, limit=limit)
            return trades
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error getting trades for {symbol}: {e}")
            return []
