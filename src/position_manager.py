import json
import os
from datetime import datetime

class PositionManager:
    def __init__(self, config, logger=None):
        self.config = config
        self.logger = logger
        self.positions = {}
        self.positions_file = 'positions.json'
        self.load_positions()
    
    def load_positions(self):
        if os.path.exists(self.positions_file):
            try:
                with open(self.positions_file, 'r') as f:
                    self.positions = json.load(f)
                if self.logger:
                    self.logger.info(f"Loaded {len(self.positions)} existing positions")
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error loading positions: {e}")
                self.positions = {}
        else:
            self.positions = {}
    
    def save_positions(self):
        import tempfile
        
        try:
            backup_file = self.positions_file + '.bak'
            if os.path.exists(self.positions_file):
                try:
                    with open(self.positions_file, 'r') as f:
                        with open(backup_file, 'w') as bak:
                            bak.write(f.read())
                except Exception:
                    pass
            
            temp_fd, temp_path = tempfile.mkstemp(suffix='.json', dir='.', text=True)
            
            try:
                with os.fdopen(temp_fd, 'w') as temp_file:
                    json.dump(self.positions, temp_file, indent=2)
                    temp_file.flush()
                    os.fsync(temp_file.fileno())
                
                with open(temp_path, 'r') as verify_file:
                    verification = json.load(verify_file)
                    if verification != self.positions:
                        raise Exception("Position verification failed - file corrupted")
                
                os.replace(temp_path, self.positions_file)
                
                if self.logger:
                    self.logger.debug(f"Positions saved and verified: {len(self.positions)} positions")
                return True
                
            except Exception as e:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                raise
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"CRITICAL: Error saving positions: {e}")
            raise Exception(f"Failed to save positions: {e}")
    
    def add_position(self, symbol, entry_price, quantity, order_id=None):
        position_data = {
            'symbol': symbol,
            'entry_price': entry_price,
            'quantity': quantity,
            'entry_time': datetime.now().isoformat(),
            'order_id': order_id,
            'highest_price': entry_price,
            'stop_loss': entry_price * (1 - self.config.stop_loss_percent / 100),
            'trailing_stop': None
        }
        
        self.positions[symbol] = position_data
        
        try:
            self.save_positions()
            if self.logger:
                self.logger.info(f"✓ Position saved successfully: {symbol} @ {entry_price}, qty: {quantity}")
        except Exception as e:
            del self.positions[symbol]
            if self.logger:
                self.logger.error(f"✗ FAILED to save position {symbol}: {e}")
                self.logger.error(f"Position ROLLED BACK from memory to prevent phantom positions!")
            raise Exception(f"Position add failed for {symbol}: {e}")
    
    def update_position(self, symbol, current_price):
        if symbol not in self.positions:
            return
        
        position = self.positions[symbol]
        old_highest = position['highest_price']
        old_trailing = position.get('trailing_stop')
        
        if current_price > position['highest_price']:
            position['highest_price'] = current_price
            
            profit_percent = ((current_price - position['entry_price']) / position['entry_price']) * 100
            
            if profit_percent > 0:
                trailing_stop_price = current_price * (1 - self.config.trailing_stop_percent / 100)
                position['trailing_stop'] = trailing_stop_price
                if self.logger:
                    self.logger.info(f"Trailing stop updated for {symbol}: {trailing_stop_price:.8f} (Current: {current_price:.8f})")
        
        try:
            self.save_positions()
        except Exception as e:
            position['highest_price'] = old_highest
            position['trailing_stop'] = old_trailing
            if self.logger:
                self.logger.error(f"Failed to save position update for {symbol}: {e}")
                self.logger.warning(f"Position update ROLLED BACK for {symbol}")
    
    def should_close_position(self, symbol, current_price):
        if symbol not in self.positions:
            return False, None
        
        position = self.positions[symbol]
        
        if current_price <= position['stop_loss']:
            loss_percent = ((current_price - position['entry_price']) / position['entry_price']) * 100
            if self.logger:
                self.logger.warning(f"Stop loss triggered for {symbol}: {loss_percent:.2f}%")
            return True, 'STOP_LOSS'
        
        if position['trailing_stop'] and current_price <= position['trailing_stop']:
            profit_percent = ((current_price - position['entry_price']) / position['entry_price']) * 100
            if self.logger:
                self.logger.info(f"Trailing stop triggered for {symbol}: {profit_percent:.2f}%")
            return True, 'TRAILING_STOP'
        
        return False, None
    
    def remove_position(self, symbol, close_price=None, reason=None):
        if symbol in self.positions:
            position = self.positions[symbol]
            position_backup = position.copy()
            
            if close_price:
                profit_percent = ((close_price - position['entry_price']) / position['entry_price']) * 100
                profit_usd = (close_price - position['entry_price']) * position['quantity']
                
                if self.logger:
                    self.logger.info(
                        f"Position closed: {symbol} | Entry: {position['entry_price']:.8f} | "
                        f"Exit: {close_price:.8f} | P/L: {profit_percent:.2f}% (${profit_usd:.2f}) | "
                        f"Reason: {reason or 'Manual'}"
                    )
                
                self.log_trade(symbol, position, close_price, profit_percent, profit_usd, reason)
            
            del self.positions[symbol]
            
            try:
                self.save_positions()
            except Exception as e:
                self.positions[symbol] = position_backup
                if self.logger:
                    self.logger.error(f"Failed to save position removal for {symbol}: {e}")
                    self.logger.warning(f"Position removal ROLLED BACK for {symbol}")
                raise Exception(f"Position removal failed for {symbol}: {e}")
    
    def log_trade(self, symbol, position, close_price, profit_percent, profit_usd, reason):
        trade_log_file = 'logs/trade_history.log'
        os.makedirs('logs', exist_ok=True)
        
        trade_data = {
            'symbol': symbol,
            'entry_time': position['entry_time'],
            'exit_time': datetime.now().isoformat(),
            'entry_price': position['entry_price'],
            'exit_price': close_price,
            'quantity': position['quantity'],
            'profit_percent': profit_percent,
            'profit_usd': profit_usd,
            'reason': reason
        }
        
        try:
            with open(trade_log_file, 'a') as f:
                f.write(json.dumps(trade_data) + '\n')
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error logging trade: {e}")
    
    def get_open_positions(self):
        return self.positions
    
    def has_position(self, symbol):
        return symbol in self.positions
    
    def get_position_count(self):
        return len(self.positions)
