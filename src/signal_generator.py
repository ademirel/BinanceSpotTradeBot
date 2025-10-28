import pandas as pd

class SignalGenerator:
    def __init__(self, config, logger=None):
        self.config = config
        self.logger = logger
        
        # Entry requirements
        self.require_ema_crossover = config.get('entry.require_ema_crossover', True)
        self.require_rsi_extreme = config.get('entry.require_rsi_extreme', True)
        self.require_heiken_ashi = config.get('entry.require_heiken_ashi', True)
        
        # Exit settings
        self.use_rsi_reversal = config.get('exit.use_rsi_reversal', True)
        self.rsi_reversal_buy_threshold = config.get('exit.rsi_reversal_buy_threshold', 30)
        self.rsi_reversal_sell_threshold = config.get('exit.rsi_reversal_sell_threshold', 70)
        self.use_ema_recross = config.get('exit.use_ema_recross', True)
    
    def generate_entry_signal(self, indicators):
        """
        Generate entry signal (BUY/SELL/HOLD)
        
        BUY conditions (all must be met):
        - EMA(21) crosses above EMA(49)
        - RSI < 10 (extreme oversold)
        - Heiken Ashi bullish confirmation
        - Passes volatility filter
        
        SELL conditions (all must be met):
        - EMA(21) crosses below EMA(49)
        - RSI > 90 (extreme overbought)
        - Heiken Ashi bearish confirmation
        - Passes volatility filter
        """
        if not indicators or 'close' not in indicators:
            return 'HOLD'
        
        # Check for required data
        required_keys = ['ema_fast', 'ema_slow', 'rsi', 'ha_bullish', 'ha_bearish', 'passes_volatility_filter']
        for key in required_keys:
            if key not in indicators:
                if self.logger:
                    self.logger.warning(f"Missing indicator: {key}")
                return 'HOLD'
        
        # Get indicator values
        ema_crossover_up = indicators.get('ema_crossover_up', False)
        ema_crossover_down = indicators.get('ema_crossover_down', False)
        rsi = indicators.get('rsi')
        rsi_oversold = indicators.get('rsi_oversold', False)
        rsi_overbought = indicators.get('rsi_overbought', False)
        ha_bullish = indicators.get('ha_bullish', False)
        ha_bearish = indicators.get('ha_bearish', False)
        passes_volatility = indicators.get('passes_volatility_filter', False)
        
        # Check for NaN
        if pd.isna(rsi):
            return 'HOLD'
        
        # BUY signal logic
        buy_conditions = []
        
        if self.require_ema_crossover:
            buy_conditions.append(ema_crossover_up)
        
        if self.require_rsi_extreme:
            buy_conditions.append(rsi_oversold)
        
        if self.require_heiken_ashi:
            buy_conditions.append(ha_bullish)
        
        # Volatility filter is always required
        buy_conditions.append(passes_volatility)
        
        if all(buy_conditions):
            if self.logger:
                self.logger.info(f"BUY signal generated: EMA crossover={ema_crossover_up}, RSI={rsi:.2f}, HA bullish={ha_bullish}, Volatility OK={passes_volatility}")
            return 'BUY'
        
        # SELL signal logic
        sell_conditions = []
        
        if self.require_ema_crossover:
            sell_conditions.append(ema_crossover_down)
        
        if self.require_rsi_extreme:
            sell_conditions.append(rsi_overbought)
        
        if self.require_heiken_ashi:
            sell_conditions.append(ha_bearish)
        
        # Volatility filter is always required
        sell_conditions.append(passes_volatility)
        
        if all(sell_conditions):
            if self.logger:
                self.logger.info(f"SELL signal generated: EMA crossover={ema_crossover_down}, RSI={rsi:.2f}, HA bearish={ha_bearish}, Volatility OK={passes_volatility}")
            return 'SELL'
        
        return 'HOLD'
    
    def check_exit_signal(self, position, indicators):
        """
        Check if position should be closed based on exit conditions
        
        Exit conditions:
        1. RSI reversal:
           - For LONG: RSI crosses above threshold (default 30)
           - For SHORT: RSI crosses below threshold (default 70)
        
        2. EMA re-cross:
           - For LONG: EMA fast crosses below EMA slow
           - For SHORT: EMA fast crosses above EMA slow
        
        3. Trailing stop (handled in order_manager)
        
        Returns: dict with exit decision and reason
        """
        if not indicators:
            return {'should_exit': False, 'reason': None}
        
        position_side = position.get('side', 'BUY')
        rsi = indicators.get('rsi')
        ema_crossover_up = indicators.get('ema_crossover_up', False)
        ema_crossover_down = indicators.get('ema_crossover_down', False)
        
        # Check RSI reversal
        if self.use_rsi_reversal and not pd.isna(rsi):
            if position_side == 'BUY':
                # Long position: exit if RSI crosses above threshold
                if rsi > self.rsi_reversal_buy_threshold:
                    return {
                        'should_exit': True,
                        'reason': f'RSI reversal (RSI={rsi:.2f} > {self.rsi_reversal_buy_threshold})'
                    }
            elif position_side == 'SELL':
                # Short position: exit if RSI crosses below threshold
                if rsi < self.rsi_reversal_sell_threshold:
                    return {
                        'should_exit': True,
                        'reason': f'RSI reversal (RSI={rsi:.2f} < {self.rsi_reversal_sell_threshold})'
                    }
        
        # Check EMA re-cross
        if self.use_ema_recross:
            if position_side == 'BUY':
                # Long position: exit if EMA fast crosses below EMA slow
                if ema_crossover_down:
                    return {
                        'should_exit': True,
                        'reason': 'EMA bearish crossover'
                    }
            elif position_side == 'SELL':
                # Short position: exit if EMA fast crosses above EMA slow
                if ema_crossover_up:
                    return {
                        'should_exit': True,
                        'reason': 'EMA bullish crossover'
                    }
        
        return {'should_exit': False, 'reason': None}
