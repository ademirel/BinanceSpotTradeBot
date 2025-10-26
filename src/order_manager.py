import time

class OrderManager:
    def __init__(self, binance_client, config, logger=None):
        self.client = binance_client
        self.config = config
        self.logger = logger
    
    def _get_trades_for_order_with_retry(self, symbol, order_id, order_time=None, max_retries=3):
        """
        Robust trade fetching with retry logic and time filtering.
        Returns list of trades for the given order_id.
        """
        for attempt in range(max_retries):
            try:
                if order_time:
                    start_time = int(order_time - 5000)
                    trades = self.client.client.get_my_trades(symbol=symbol, startTime=start_time, limit=100)
                else:
                    trades = self.client.get_my_trades(symbol, limit=100)
                
                order_trades = [t for t in trades if t.get('orderId') == order_id]
                
                if order_trades:
                    return order_trades
                
                if attempt < max_retries - 1:
                    if self.logger:
                        self.logger.debug(f"No trades found for order {order_id}, retrying... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(1 * (attempt + 1))
                
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error fetching trades for {symbol} order {order_id}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1 * (attempt + 1))
        
        return []
    
    def _calculate_avg_price_from_trades(self, trades, fallback_price):
        """
        Calculate average execution price from trades.
        Returns (avg_price, total_quantity).
        """
        if not trades:
            return fallback_price, 0
        
        total_cost = sum(float(t['price']) * float(t['qty']) for t in trades)
        total_qty = sum(float(t['qty']) for t in trades)
        
        if total_qty > 0:
            avg_price = total_cost / total_qty
            return avg_price, total_qty
        
        return fallback_price, 0
    
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
                self.logger.warning(f"Skip {symbol}: Calculated quantity {quantity} < minimum {min_qty} (Need ${(min_qty * price):.2f} minimum, have ${amount_usd})")
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
            order_time = order.get('transactTime')
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
                        order_trades = self._get_trades_for_order_with_retry(symbol, order_id, order_time)
                        avg_price, trade_qty = self._calculate_avg_price_from_trades(order_trades, limit_price)
                    
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
                    
                    if executed_qty == 0:
                        if self.logger:
                            self.logger.debug(f"Order {status} with executedQty=0, checking trades to confirm...")
                        
                        time.sleep(0.5)
                        retry_status = self.client.get_order_status(symbol, order_id)
                        if retry_status:
                            executed_qty = float(retry_status.get('executedQty', 0))
                        
                        if executed_qty == 0:
                            order_trades = self._get_trades_for_order_with_retry(symbol, order_id, order_time)
                            if order_trades:
                                avg_price, executed_qty = self._calculate_avg_price_from_trades(order_trades, limit_price)
                                if executed_qty > 0:
                                    if self.logger:
                                        self.logger.warning(f"Order {status} but found execution via trades for {symbol}: {executed_qty} @ {avg_price}")
                                    return {
                                        'symbol': symbol,
                                        'price': avg_price,
                                        'quantity': executed_qty,
                                        'order_id': order_id
                                    }
                    
                    if executed_qty > 0:
                        fills = order_status.get('fills', [])
                        if fills:
                            avg_price = sum(float(fill['price']) * float(fill['qty']) for fill in fills) / sum(float(fill['qty']) for fill in fills)
                        else:
                            avg_price = float(order_status.get('price', 0))
                        
                        if avg_price == 0:
                            order_trades = self._get_trades_for_order_with_retry(symbol, order_id, order_time)
                            avg_price, _ = self._calculate_avg_price_from_trades(order_trades, limit_price)
                        
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
            
            time.sleep(1.5)
            final_status = self.client.get_order_status(symbol, order_id)
            
            if not final_status:
                if self.logger:
                    self.logger.warning(f"Could not get final order status for {symbol}, checking trades with retry...")
                
                order_trades = self._get_trades_for_order_with_retry(symbol, order_id, order_time)
                if order_trades:
                    avg_price, total_qty = self._calculate_avg_price_from_trades(order_trades, limit_price)
                    if total_qty > 0:
                        if self.logger:
                            self.logger.warning(f"Found execution via trades for {symbol}: {total_qty} @ {avg_price}")
                        return {
                            'symbol': symbol,
                            'price': avg_price,
                            'quantity': total_qty,
                            'order_id': order_id
                        }
                return None
            
            executed_qty = float(final_status.get('executedQty', 0))
            
            if executed_qty == 0:
                if self.logger:
                    self.logger.debug(f"Final status shows executedQty=0, double-checking with trades...")
                
                order_trades = self._get_trades_for_order_with_retry(symbol, order_id, order_time)
                if order_trades:
                    avg_price, executed_qty = self._calculate_avg_price_from_trades(order_trades, limit_price)
                    if executed_qty > 0:
                        if self.logger:
                            self.logger.warning(f"Found execution via trades despite executedQty=0 for {symbol}: {executed_qty} @ {avg_price}")
                        return {
                            'symbol': symbol,
                            'price': avg_price,
                            'quantity': executed_qty,
                            'order_id': order_id
                        }
                return None
            
            if executed_qty > 0:
                fills = final_status.get('fills', [])
                if fills:
                    avg_price = sum(float(fill['price']) * float(fill['qty']) for fill in fills) / sum(float(fill['qty']) for fill in fills)
                else:
                    avg_price = float(final_status.get('price', 0))
                
                if avg_price == 0:
                    order_trades = self._get_trades_for_order_with_retry(symbol, order_id, order_time)
                    avg_price, _ = self._calculate_avg_price_from_trades(order_trades, limit_price)
                
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
