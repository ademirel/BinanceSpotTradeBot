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
            if self.logger:
                self.logger.error(f"Could not get LOT_SIZE filter for {symbol}")
            return None
        
        quantity = amount_usd / price
        
        quantity = self.round_step_size(quantity, step_size)
        
        if quantity < min_qty:
            if self.logger:
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
            
            if self.logger:
                self.logger.info(f"Placing limit buy for {symbol}: {quantity} @ {limit_price}")
            
            order = self.client.create_limit_buy_order(symbol, quantity, str(limit_price))
            
            if not order:
                return None
            
            order_id = order.get('orderId')
            if not order_id:
                return None
            
            max_wait_time = 30
            check_interval = 2
            elapsed = 0
            
            while elapsed < max_wait_time:
                time.sleep(check_interval)
                elapsed += check_interval
                
                order_status = self.client.get_order_status(symbol, order_id)
                if not order_status:
                    continue
                
                status = order_status.get('status')
                
                if status == 'FILLED':
                    executed_qty = float(order_status.get('executedQty', 0))
                    fills = order_status.get('fills', [])
                    
                    if fills:
                        avg_price = sum(float(fill['price']) * float(fill['qty']) for fill in fills) / sum(float(fill['qty']) for fill in fills)
                    else:
                        avg_price = float(order_status.get('price', 0))
                    
                    if avg_price == 0:
                        recent_trades = self.client.get_my_trades(symbol, limit=50)
                        order_trades = [t for t in recent_trades if t.get('orderId') == order_id]
                        if order_trades:
                            total_cost = sum(float(t['price']) * float(t['qty']) for t in order_trades)
                            total_qty = sum(float(t['qty']) for t in order_trades)
                            avg_price = total_cost / total_qty if total_qty > 0 else limit_price
                        else:
                            avg_price = limit_price
                    
                    if self.logger:
                        self.logger.info(f"Order FILLED for {symbol}: {executed_qty} @ {avg_price}")
                    
                    return {
                        'symbol': symbol,
                        'price': avg_price,
                        'quantity': executed_qty,
                        'order_id': order_id
                    }
                
                elif status in ['CANCELED', 'REJECTED', 'EXPIRED']:
                    executed_qty = float(order_status.get('executedQty', 0))
                    
                    if executed_qty > 0:
                        fills = order_status.get('fills', [])
                        if fills:
                            avg_price = sum(float(fill['price']) * float(fill['qty']) for fill in fills) / sum(float(fill['qty']) for fill in fills)
                        else:
                            avg_price = float(order_status.get('price', 0))
                        
                        if avg_price == 0:
                            recent_trades = self.client.get_my_trades(symbol, limit=50)
                            order_trades = [t for t in recent_trades if t.get('orderId') == order_id]
                            if order_trades:
                                total_cost = sum(float(t['price']) * float(t['qty']) for t in order_trades)
                                total_qty = sum(float(t['qty']) for t in order_trades)
                                avg_price = total_cost / total_qty if total_qty > 0 else limit_price
                            else:
                                avg_price = limit_price
                        
                        if self.logger:
                            self.logger.warning(f"Order {status} but partially filled for {symbol}: {executed_qty} @ {avg_price}")
                        
                        return {
                            'symbol': symbol,
                            'price': avg_price,
                            'quantity': executed_qty,
                            'order_id': order_id
                        }
                    
                    if self.logger:
                        self.logger.warning(f"Order {status} for {symbol}")
                    return None
            
            if self.logger:
                self.logger.warning(f"Order timeout for {symbol}, attempting to cancel...")
            
            cancel_result = self.client.cancel_order(symbol, order_id)
            
            time.sleep(1)
            final_status = self.client.get_order_status(symbol, order_id)
            
            if not final_status:
                if self.logger:
                    self.logger.warning(f"Could not get final order status for {symbol}, checking trades...")
                recent_trades = self.client.get_my_trades(symbol, limit=50)
                order_trades = [t for t in recent_trades if t.get('orderId') == order_id]
                if order_trades:
                    total_cost = sum(float(t['price']) * float(t['qty']) for t in order_trades)
                    total_qty = sum(float(t['qty']) for t in order_trades)
                    if total_qty > 0:
                        avg_price = total_cost / total_qty
                        if self.logger:
                            self.logger.warning(f"Found partial fill via trades for {symbol}: {total_qty} @ {avg_price}")
                        return {
                            'symbol': symbol,
                            'price': avg_price,
                            'quantity': total_qty,
                            'order_id': order_id
                        }
                return None
            
            executed_qty = float(final_status.get('executedQty', 0))
            
            if executed_qty > 0:
                fills = final_status.get('fills', [])
                if fills:
                    avg_price = sum(float(fill['price']) * float(fill['qty']) for fill in fills) / sum(float(fill['qty']) for fill in fills)
                else:
                    avg_price = float(final_status.get('price', 0))
                
                if avg_price == 0:
                    recent_trades = self.client.get_my_trades(symbol, limit=50)
                    order_trades = [t for t in recent_trades if t.get('orderId') == order_id]
                    if order_trades:
                        total_cost = sum(float(t['price']) * float(t['qty']) for t in order_trades)
                        total_qty = sum(float(t['qty']) for t in order_trades)
                        avg_price = total_cost / total_qty if total_qty > 0 else limit_price
                    else:
                        avg_price = limit_price
                
                if self.logger:
                    self.logger.warning(f"Order partially filled for {symbol}: {executed_qty} @ {avg_price}")
                
                return {
                    'symbol': symbol,
                    'price': avg_price,
                    'quantity': executed_qty,
                    'order_id': order_id
                }
            
            return None
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error placing limit buy for {symbol}: {e}")
            return None
    
    def close_position(self, symbol, quantity):
        try:
            if self.logger:
                self.logger.info(f"Closing position for {symbol}: {quantity}")
            
            base_asset = symbol.replace('USDT', '')
            actual_balance = self.client.get_asset_balance_quantity(base_asset)
            
            if actual_balance < quantity * 0.99:
                if self.logger:
                    self.logger.warning(f"Actual balance {actual_balance} < expected {quantity} for {symbol}, using actual balance")
                quantity = actual_balance
            
            if quantity == 0:
                if self.logger:
                    self.logger.error(f"Cannot close position for {symbol}: zero balance")
                return None
            
            min_qty, max_qty, step_size = self.get_lot_size_filter(symbol)
            if min_qty:
                quantity = self.round_step_size(quantity, step_size)
            
            order = self.client.create_market_sell_order(symbol, str(quantity))
            
            if order:
                fills = order.get('fills', [])
                if fills:
                    avg_price = sum(float(fill['price']) * float(fill['qty']) for fill in fills) / sum(float(fill['qty']) for fill in fills)
                    return avg_price
                
                return self.client.get_symbol_price(symbol)
            
            return None
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error closing position for {symbol}: {e}")
            return None
