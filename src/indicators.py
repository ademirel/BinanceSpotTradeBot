import pandas as pd
import pandas_ta as ta
import numpy as np

class TechnicalIndicators:
    def __init__(self, config, logger=None):
        self.config = config
        self.logger = logger
        
        # EMA settings
        self.ema_fast = config.get('indicators.ema.fast', 21)
        self.ema_slow = config.get('indicators.ema.slow', 49)
        
        # RSI settings
        self.rsi_period = config.get('indicators.rsi.period', 14)
        self.rsi_oversold = config.get('indicators.rsi.oversold', 10)
        self.rsi_overbought = config.get('indicators.rsi.overbought', 90)
        
        # ATR settings
        self.atr_period = config.get('indicators.atr.period', 14)
        self.atr_lookback = config.get('indicators.atr.lookback_for_average', 50)
        
        # Heiken Ashi settings
        self.ha_enabled = config.get('indicators.heiken_ashi.enabled', True)
        self.ha_min_body_percent = config.get('indicators.heiken_ashi.min_body_percent', 0.3)
        
        # Volatility filter
        self.volatility_enabled = config.get('volatility.enabled', True)
        self.atr_multiplier = config.get('volatility.atr_multiplier', 1.5)
    
    def _prepare_dataframe(self, klines):
        """Convert klines to DataFrame with proper types"""
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        
        return df
    
    def calculate_heiken_ashi(self, df):
        """
        Calculate Heiken Ashi candles
        Returns DataFrame with ha_open, ha_high, ha_low, ha_close
        """
        ha = df.copy()
        
        # HA Close = (O + H + L + C) / 4
        ha['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
        
        # HA Open - initialize
        ha['ha_open'] = 0.0
        ha.loc[ha.index[0], 'ha_open'] = (df.loc[df.index[0], 'open'] + df.loc[df.index[0], 'close']) / 2
        
        # HA Open - calculate for remaining candles
        for i in range(1, len(ha)):
            ha.loc[ha.index[i], 'ha_open'] = (ha.loc[ha.index[i-1], 'ha_open'] + ha.loc[ha.index[i-1], 'ha_close']) / 2
        
        # HA High = max(H, HA_Open, HA_Close)
        ha['ha_high'] = ha[['high', 'ha_open', 'ha_close']].max(axis=1)
        
        # HA Low = min(L, HA_Open, HA_Close)
        ha['ha_low'] = ha[['low', 'ha_open', 'ha_close']].min(axis=1)
        
        return ha
    
    def check_heiken_ashi_signal(self, ha_df, direction='buy'):
        """
        Check Heiken Ashi confirmation for entry
        
        Buy confirmation:
        - HA candle is bullish (ha_close > ha_open)
        - Strong body (body size > min_body_percent of total range)
        
        Sell confirmation:
        - HA candle is bearish (ha_close < ha_open)
        - Strong body
        """
        if len(ha_df) < 1:
            return False
        
        latest = ha_df.iloc[-1]
        
        ha_open = latest['ha_open']
        ha_close = latest['ha_close']
        ha_high = latest['ha_high']
        ha_low = latest['ha_low']
        
        # Calculate body and range
        body = abs(ha_close - ha_open)
        total_range = ha_high - ha_low
        
        if total_range == 0:
            return False
        
        body_percent = body / total_range
        
        # Check body size requirement
        if body_percent < self.ha_min_body_percent:
            return False
        
        # Check direction
        if direction == 'buy':
            return ha_close > ha_open
        elif direction == 'sell':
            return ha_close < ha_open
        
        return False
    
    def calculate_indicators(self, klines):
        """
        Calculate all technical indicators
        Returns dict with indicator values and signals
        """
        # Minimum data requirement
        min_required = max(self.ema_slow, self.rsi_period, self.atr_period, self.atr_lookback) + 10
        
        if not klines or len(klines) < min_required:
            if self.logger:
                self.logger.warning(f"Insufficient data: {len(klines) if klines else 0} candles, need {min_required}")
            return None
        
        df = self._prepare_dataframe(klines)
        
        # Calculate EMA
        df['ema_fast'] = ta.ema(df['close'], length=self.ema_fast)
        df['ema_slow'] = ta.ema(df['close'], length=self.ema_slow)
        
        # Calculate RSI
        df['rsi'] = ta.rsi(df['close'], length=self.rsi_period)
        
        # Calculate ATR
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=self.atr_period)
        
        # Calculate Heiken Ashi
        ha_df = self.calculate_heiken_ashi(df)
        
        # Get latest values
        latest = df.iloc[-1]
        previous = df.iloc[-2]
        
        result = {
            # Raw values
            'close': latest['close'],
            'open': latest['open'],
            'high': latest['high'],
            'low': latest['low'],
            
            # EMA
            'ema_fast': latest['ema_fast'],
            'ema_slow': latest['ema_slow'],
            
            # RSI
            'rsi': latest['rsi'],
            
            # ATR
            'atr': latest['atr'],
            
            # Heiken Ashi
            'ha_open': ha_df['ha_open'].iloc[-1],
            'ha_close': ha_df['ha_close'].iloc[-1],
            'ha_high': ha_df['ha_high'].iloc[-1],
            'ha_low': ha_df['ha_low'].iloc[-1],
        }
        
        # Check for NaN values
        if pd.isna(result['ema_fast']) or pd.isna(result['ema_slow']) or pd.isna(result['rsi']) or pd.isna(result['atr']):
            if self.logger:
                self.logger.warning("NaN values in indicators")
            return None
        
        # EMA Crossover detection
        result['ema_crossover_up'] = False
        result['ema_crossover_down'] = False
        
        if not pd.isna(previous['ema_fast']) and not pd.isna(previous['ema_slow']):
            # Bullish crossover: EMA fast crosses above EMA slow
            if previous['ema_fast'] <= previous['ema_slow'] and latest['ema_fast'] > latest['ema_slow']:
                result['ema_crossover_up'] = True
            
            # Bearish crossover: EMA fast crosses below EMA slow
            if previous['ema_fast'] >= previous['ema_slow'] and latest['ema_fast'] < latest['ema_slow']:
                result['ema_crossover_down'] = True
        
        # EMA position
        result['ema_fast_above_slow'] = latest['ema_fast'] > latest['ema_slow']
        
        # RSI signals
        result['rsi_oversold'] = latest['rsi'] < self.rsi_oversold
        result['rsi_overbought'] = latest['rsi'] > self.rsi_overbought
        
        # Heiken Ashi confirmation
        result['ha_bullish'] = self.check_heiken_ashi_signal(ha_df, direction='buy')
        result['ha_bearish'] = self.check_heiken_ashi_signal(ha_df, direction='sell')
        
        # Volatility filter
        result['passes_volatility_filter'] = self.check_volatility_filter(df)
        
        # Average ATR for reference
        if len(df) >= self.atr_lookback:
            result['atr_average'] = df['atr'].iloc[-self.atr_lookback:].mean()
        else:
            result['atr_average'] = result['atr']
        
        return result
    
    def check_volatility_filter(self, df):
        """
        Check if current ATR is above threshold
        ATR > average ATR × multiplier
        """
        if not self.volatility_enabled:
            return True
        
        if len(df) < self.atr_lookback:
            return False
        
        current_atr = df['atr'].iloc[-1]
        avg_atr = df['atr'].iloc[-self.atr_lookback:].mean()
        
        if pd.isna(current_atr) or pd.isna(avg_atr) or avg_atr == 0:
            return False
        
        return current_atr > (avg_atr * self.atr_multiplier)
    
    def get_atr_for_trailing_stop(self, klines):
        """
        Get current ATR value for trailing stop calculation
        """
        if not klines or len(klines) < self.atr_period + 5:
            return None
        
        df = self._prepare_dataframe(klines)
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=self.atr_period)
        
        current_atr = df['atr'].iloc[-1]
        
        if pd.isna(current_atr):
            return None
        
        return current_atr
