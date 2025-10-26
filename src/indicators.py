import pandas as pd
import pandas_ta as ta
import numpy as np

class TechnicalIndicators:
    def __init__(self, config, logger=None):
        self.config = config
        self.logger = logger
        
        self.rsi_period = config.get('indicators.rsi.period', 14)
        self.macd_fast = config.get('indicators.macd.fast_period', 12)
        self.macd_slow = config.get('indicators.macd.slow_period', 26)
        self.macd_signal = config.get('indicators.macd.signal_period', 9)
        self.ma_short = config.get('indicators.moving_averages.short_period', 20)
        self.ma_long = config.get('indicators.moving_averages.long_period', 50)
    
    def calculate_indicators(self, klines):
        if not klines or len(klines) < self.ma_long:
            return None
        
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        df['close'] = df['close'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['volume'] = df['volume'].astype(float)
        
        df['rsi'] = ta.rsi(df['close'], length=self.rsi_period)
        
        macd = ta.macd(df['close'], fast=self.macd_fast, slow=self.macd_slow, signal=self.macd_signal)
        if macd is not None:
            df['macd'] = macd[f'MACD_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}']
            df['macd_signal'] = macd[f'MACDs_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}']
            df['macd_hist'] = macd[f'MACDh_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}']
        
        df['sma_short'] = ta.sma(df['close'], length=self.ma_short)
        df['sma_long'] = ta.sma(df['close'], length=self.ma_long)
        
        return df.iloc[-1].to_dict()
    
    def get_last_n_closes(self, klines, n=5):
        if not klines or len(klines) < n:
            return []
        
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        df['close'] = df['close'].astype(float)
        
        return df['close'].tail(n).tolist()
