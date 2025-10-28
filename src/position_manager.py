import json
import os
from datetime import datetime, timezone

class PositionManager:
    def __init__(self, config, logger=None):
        self.config = config
        self.logger = logger
        self.positions = {}
        self.positions_file = 'positions.json'
        self.daily_pnl_file = 'daily_pnl.json'
        
        # Risk management settings
        self.max_positions = config.get('risk_management.max_positions', 5)
        self.position_size_percent = config.get('risk_management.position_size_percent', 25)
        self.daily_loss_limit_percent = config.get('risk_management.daily_loss_limit_percent', 3.0)
        self.daily_profit_protection_percent = config.get('risk_management.daily_profit_protection_percent', 3.0)
        self.protection_mode_behavior = config.get('risk_management.protection_mode_behavior', 'stop_new_entries')
        
        # Daily tracking settings
        self.reset_hour_utc = config.get('daily_tracking.reset_hour_utc', 0)
        self.track_realized_only = config.get('daily_tracking.track_realized_only', True)
        
        self.load_positions()
        self.load_daily_pnl()
    
    def load_positions(self):
        """Load open positions from file"""
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
        """Save positions with atomic write and verification"""
        import tempfile
        
        try:
            # Create backup
            backup_file = self.positions_file + '.bak'
            if os.path.exists(self.positions_file):
                try:
                    with open(self.positions_file, 'r') as f:
                        with open(backup_file, 'w') as bak:
                            bak.write(f.read())
                except Exception:
                    pass
            
            # Write to temp file
            temp_fd, temp_path = tempfile.mkstemp(suffix='.json', dir='.', text=True)
            
            try:
                with os.fdopen(temp_fd, 'w') as temp_file:
                    json.dump(self.positions, temp_file, indent=2)
                    temp_file.flush()
                    os.fsync(temp_file.fileno())
                
                # Verify
                with open(temp_path, 'r') as verify_file:
                    verification = json.load(verify_file)
                    if verification != self.positions:
                        raise Exception("Position verification failed - file corrupted")
                
                # Atomic replace
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
    
    def load_daily_pnl(self):
        """Load daily P&L data"""
        if os.path.exists(self.daily_pnl_file):
            try:
                with open(self.daily_pnl_file, 'r') as f:
                    self.daily_pnl = json.load(f)
                
                # Check if we need to reset (new day)
                if self._should_reset_daily_pnl():
                    self._reset_daily_pnl()
                
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error loading daily P&L: {e}")
                self._reset_daily_pnl()
        else:
            self._reset_daily_pnl()
    
    def save_daily_pnl(self):
        """Save daily P&L data"""
        try:
            with open(self.daily_pnl_file, 'w') as f:
                json.dump(self.daily_pnl, f, indent=2)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error saving daily P&L: {e}")
    
    def _should_reset_daily_pnl(self):
        """Check if daily P&L should be reset"""
        if 'reset_date' not in self.daily_pnl:
            return True
        
        last_reset = datetime.fromisoformat(self.daily_pnl['reset_date'])
        now = datetime.now(timezone.utc)
        
        # Check if it's a new day past reset hour
        if now.date() > last_reset.date():
            if now.hour >= self.reset_hour_utc:
                return True
        
        return False
    
    def _reset_daily_pnl(self):
        """Reset daily P&L"""
        self.daily_pnl = {
            'reset_date': datetime.now(timezone.utc).isoformat(),
            'realized_pnl': 0.0,
            'unrealized_pnl': 0.0,
            'total_pnl': 0.0,
            'trades_count': 0,
            'wins': 0,
            'losses': 0
        }
        self.save_daily_pnl()
        
        if self.logger:
            self.logger.info("Daily P&L reset")
    
    def get_daily_pnl(self):
        """Get current daily P&L"""
        return self.daily_pnl.copy()
    
    def is_in_protection_mode(self):
        """Check if in profit protection mode (daily profit > threshold)"""
        if self.protection_mode_behavior == 'disabled':
            return False
        
        total_pnl_percent = self.daily_pnl.get('total_pnl', 0.0)
        
        return total_pnl_percent >= self.daily_profit_protection_percent
    
    def has_hit_daily_loss_limit(self):
        """Check if daily loss limit has been hit"""
        total_pnl_percent = self.daily_pnl.get('total_pnl', 0.0)
        
        return total_pnl_percent <= -self.daily_loss_limit_percent
    
    def can_open_new_position(self, symbol):
        """Check if new position can be opened"""
        # Check if already have position
        if symbol in self.positions:
            return False, "Already have position in this symbol"
        
        # Check max positions limit
        if len(self.positions) >= self.max_positions:
            return False, f"Max positions limit reached ({self.max_positions})"
        
        # Check protection mode
        if self.is_in_protection_mode():
            return False, f"Profit protection mode active ({self.daily_pnl.get('total_pnl', 0):.2f}% profit)"
        
        # Check daily loss limit
        if self.has_hit_daily_loss_limit():
            return False, f"Daily loss limit hit ({self.daily_pnl.get('total_pnl', 0):.2f}%)"
        
        return True, "OK"
    
    def calculate_position_size(self, current_price, account_balance):
        """
        Calculate position size based on portfolio percentage
        Returns quantity to buy
        """
        # Use position_size_percent of portfolio
        position_value_usd = account_balance * (self.position_size_percent / 100)
        
        # Calculate quantity
        quantity = position_value_usd / current_price
        
        return quantity, position_value_usd
    
    def add_position(self, symbol, entry_price, quantity, side='BUY', order_id=None, initial_stop_percent=None):
        """Add new position"""
        if initial_stop_percent is None:
            initial_stop_percent = self.config.get('exit.trailing_stop.initial_percent', 2.5)
        
        # Calculate initial stop
        if side == 'BUY':
            stop_loss = entry_price * (1 - initial_stop_percent / 100)
        else:
            stop_loss = entry_price * (1 + initial_stop_percent / 100)
        
        position_data = {
            'symbol': symbol,
            'side': side,
            'entry_price': entry_price,
            'quantity': quantity,
            'entry_time': datetime.now(timezone.utc).isoformat(),
            'order_id': order_id,
            'highest_price': entry_price if side == 'BUY' else None,
            'lowest_price': entry_price if side == 'SELL' else None,
            'stop_loss': stop_loss,
            'trailing_stop': None,
            'initial_stop_percent': initial_stop_percent
        }
        
        self.positions[symbol] = position_data
        
        try:
            self.save_positions()
            if self.logger:
                self.logger.info(f"✓ Position saved: {symbol} {side} @ {entry_price}, qty: {quantity}, stop: {stop_loss:.8f}")
        except Exception as e:
            del self.positions[symbol]
            if self.logger:
                self.logger.error(f"✗ FAILED to save position {symbol}: {e}")
            raise Exception(f"Position add failed for {symbol}: {e}")
    
    def update_trailing_stop(self, symbol, current_price, atr_value=None):
        """
        Update trailing stop using ATR-based calculation
        """
        if symbol not in self.positions:
            return
        
        position = self.positions[symbol]
        side = position.get('side', 'BUY')
        
        old_stop = position.get('trailing_stop')
        
        # Get ATR multiplier from config
        atr_multiplier = self.config.get('exit.trailing_stop.atr_multiplier', 2.0)
        initial_percent = position.get('initial_stop_percent', 2.5)
        
        # Calculate new stop
        if atr_value and atr_value > 0:
            # ATR-based stop
            stop_distance = atr_value * atr_multiplier
        else:
            # Fallback to percentage-based
            stop_distance = current_price * (initial_percent / 100)
        
        if side == 'BUY':
            # Long position
            if current_price > position.get('highest_price', position['entry_price']):
                position['highest_price'] = current_price
            
            new_trailing_stop = current_price - stop_distance
            
            # Only tighten, never loosen
            if old_stop is None or new_trailing_stop > old_stop:
                position['trailing_stop'] = new_trailing_stop
                
                if self.logger:
                    self.logger.debug(f"Trailing stop updated {symbol}: {new_trailing_stop:.8f} (price: {current_price:.8f}, ATR: {atr_value:.8f if atr_value else 'N/A'})")
        
        else:
            # Short position
            if current_price < position.get('lowest_price', position['entry_price']):
                position['lowest_price'] = current_price
            
            new_trailing_stop = current_price + stop_distance
            
            # Only tighten, never loosen
            if old_stop is None or new_trailing_stop < old_stop:
                position['trailing_stop'] = new_trailing_stop
                
                if self.logger:
                    self.logger.debug(f"Trailing stop updated {symbol}: {new_trailing_stop:.8f} (price: {current_price:.8f}, ATR: {atr_value:.8f if atr_value else 'N/A'})")
        
        try:
            self.save_positions()
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to save trailing stop update for {symbol}: {e}")
    
    def should_close_position(self, symbol, current_price):
        """Check if position should be closed based on stops"""
        if symbol not in self.positions:
            return False, None
        
        position = self.positions[symbol]
        side = position.get('side', 'BUY')
        
        if side == 'BUY':
            # Long position
            if current_price <= position['stop_loss']:
                loss_percent = ((current_price - position['entry_price']) / position['entry_price']) * 100
                if self.logger:
                    self.logger.warning(f"Stop loss triggered {symbol}: {loss_percent:.2f}%")
                return True, 'STOP_LOSS'
            
            if position.get('trailing_stop') and current_price <= position['trailing_stop']:
                profit_percent = ((current_price - position['entry_price']) / position['entry_price']) * 100
                if self.logger:
                    self.logger.info(f"Trailing stop triggered {symbol}: {profit_percent:.2f}%")
                return True, 'TRAILING_STOP'
        
        else:
            # Short position
            if current_price >= position['stop_loss']:
                loss_percent = ((position['entry_price'] - current_price) / position['entry_price']) * 100
                if self.logger:
                    self.logger.warning(f"Stop loss triggered {symbol}: {loss_percent:.2f}%")
                return True, 'STOP_LOSS'
            
            if position.get('trailing_stop') and current_price >= position['trailing_stop']:
                profit_percent = ((position['entry_price'] - current_price) / position['entry_price']) * 100
                if self.logger:
                    self.logger.info(f"Trailing stop triggered {symbol}: {profit_percent:.2f}%")
                return True, 'TRAILING_STOP'
        
        return False, None
    
    def remove_position(self, symbol, close_price=None, reason=None):
        """Remove position and update daily P&L"""
        if symbol in self.positions:
            position = self.positions[symbol]
            position_backup = position.copy()
            
            if close_price:
                # Calculate P&L
                side = position.get('side', 'BUY')
                
                if side == 'BUY':
                    profit_percent = ((close_price - position['entry_price']) / position['entry_price']) * 100
                    profit_usd = (close_price - position['entry_price']) * position['quantity']
                else:
                    profit_percent = ((position['entry_price'] - close_price) / position['entry_price']) * 100
                    profit_usd = (position['entry_price'] - close_price) * position['quantity']
                
                # Update daily P&L
                self.daily_pnl['realized_pnl'] += profit_usd
                self.daily_pnl['trades_count'] += 1
                
                if profit_usd > 0:
                    self.daily_pnl['wins'] += 1
                else:
                    self.daily_pnl['losses'] += 1
                
                # Recalculate total P&L
                # Note: This is simplified - in production you'd track account balance
                self.daily_pnl['total_pnl'] += profit_percent
                
                self.save_daily_pnl()
                
                if self.logger:
                    self.logger.info(
                        f"Position closed: {symbol} {side} | Entry: {position['entry_price']:.8f} | "
                        f"Exit: {close_price:.8f} | P/L: {profit_percent:.2f}% (${profit_usd:.2f}) | "
                        f"Reason: {reason or 'Manual'} | Daily P&L: {self.daily_pnl['total_pnl']:.2f}%"
                    )
                
                self.log_trade(symbol, position, close_price, profit_percent, profit_usd, reason)
            
            del self.positions[symbol]
            
            try:
                self.save_positions()
            except Exception as e:
                self.positions[symbol] = position_backup
                if self.logger:
                    self.logger.error(f"Failed to save position removal for {symbol}: {e}")
                raise Exception(f"Position removal failed for {symbol}: {e}")
    
    def log_trade(self, symbol, position, close_price, profit_percent, profit_usd, reason):
        """Log completed trade"""
        trade_log_file = 'logs/trade_history.log'
        os.makedirs('logs', exist_ok=True)
        
        trade_data = {
            'symbol': symbol,
            'side': position.get('side', 'BUY'),
            'entry_time': position['entry_time'],
            'exit_time': datetime.now(timezone.utc).isoformat(),
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
        """Get all open positions"""
        return self.positions
    
    def has_position(self, symbol):
        """Check if have position in symbol"""
        return symbol in self.positions
    
    def get_position_count(self):
        """Get number of open positions"""
        return len(self.positions)
    
    def get_position(self, symbol):
        """Get specific position"""
        return self.positions.get(symbol)
