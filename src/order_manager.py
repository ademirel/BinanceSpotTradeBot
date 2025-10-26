import time

class OrderManager:
    def __init__(self, binance_client, config, logger=None):
        self.client = binance_client
        self.config = config
        self.logger = logger
    
    def get_lot_size_filter(self, symbol):
        symbol_info = self.client.get_symbol_info(symbol)
        if not symbol_info:
            return None, None, None
        
        for filter_item in symbol_info['filters']:
            if filter_item['filterType'] == 'LOT_SIZE':
                return (
                    float(filter_item['minQty']),
                    float(filter_item['maxQty']),
                    float(filter_item['stepSize'])
                )
        
        return None, None, None
    
    def get_price_filter(self, symbol):
        symbol_info = self.client.get_symbol_info(symbol)
        if not symbol_info:
            return None, None
        
        for filter_item in symbol_info['filters']:
            if filter_item['filterType'] == 'PRICE_FILTER':
                return float(filter_item['tickSize']), float(filter_item['minPrice'])
        
        return None, None
    
    def round_step_size(self, quantity, step_size):
        precision = len(str(step_size).split('.')[-1].rstrip('0'))
        return round(quantity - (quantity % step_size), precision)
    
    def round_price(self, price, tick_size):
        precision = len(str(tick_size).split('.')[-1].rstrip('0'))
        return round(price - (price % tick_size), precision)
    
    def calculate_quantity(self, symbol, price, amount_usd):
        min_qty, max_qty, step_size = self.get_lot_size_filter(symbol)
        
        if not min_qty:
            self.logger.error(f"Could not get LOT_SIZE filter for {symbol}")
            return None
        
        quantity = amount_usd / price
        
        quantity = self.round_step_size(quantity, step_size)
        
        if quantity < min_qty:
            self.logger.warning(f"Calculated quantity {quantity} is less than min {min_qty} for {symbol}")
            return None
        
        if max_qty and quantity > max_qty:
            quantity = max_qty
        
        return quantity
    
    def place_limit_buy(self, symbol, amount_usd):
        try:
            current_price = self.client.get_symbol_price(symbol)
            if not current_price:
                return None
            
            tick_size, min_price = self.get_price_filter(symbol)
            if not tick_size:
                return None
            
            limit_price = current_price * 0.998
            limit_price = self.round_price(limit_price, tick_size)
            
            quantity = self.calculate_quantity(symbol, limit_price, amount_usd)
            if not quantity:
                return None
            
            self.logger.info(f"Placing limit buy for {symbol}: {quantity} @ {limit_price}")
            
            order = self.client.create_limit_buy_order(symbol, quantity, str(limit_price))
            
            if order:
                time.sleep(2)
                
                return {
                    'symbol': symbol,
                    'price': limit_price,
                    'quantity': quantity,
                    'order_id': order.get('orderId')
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error placing limit buy for {symbol}: {e}")
            return None
    
    def close_position(self, symbol, quantity):
        try:
            self.logger.info(f"Closing position for {symbol}: {quantity}")
            
            order = self.client.create_market_sell_order(symbol, quantity)
            
            if order:
                fills = order.get('fills', [])
                if fills:
                    avg_price = sum(float(fill['price']) * float(fill['qty']) for fill in fills) / sum(float(fill['qty']) for fill in fills)
                    return avg_price
                
                return self.client.get_symbol_price(symbol)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error closing position for {symbol}: {e}")
            return None
