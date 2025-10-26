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
        self.ema_fast = config.get('indicators.ema.fast_period', 12)
        self.ema_slow = config.get('indicators.ema.slow_period', 26)
        self.bb_period = config.get('indicators.bollinger.period', 20)
        self.bb_std = config.get('indicators.bollinger.std_dev', 2)
        self.atr_period = config.get('indicators.atr.period', 14)
        self.adx_period = config.get('indicators.adx.period', 14)
    
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
        df['open'] = df['open'].astype(float)
        df['volume'] = df['volume'].astype(float)
        
        df['rsi'] = ta.rsi(df['close'], length=self.rsi_period)
        
        macd = ta.macd(df['close'], fast=self.macd_fast, slow=self.macd_slow, signal=self.macd_signal)
        if macd is not None:
            df['macd'] = macd[f'MACD_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}']
            df['macd_signal'] = macd[f'MACDs_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}']
            df['macd_hist'] = macd[f'MACDh_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}']
        
        df['sma_short'] = ta.sma(df['close'], length=self.ma_short)
        df['sma_long'] = ta.sma(df['close'], length=self.ma_long)
        
        df['ema_fast'] = ta.ema(df['close'], length=self.ema_fast)
        df['ema_slow'] = ta.ema(df['close'], length=self.ema_slow)
        
        bbands = ta.bbands(df['close'], length=self.bb_period, std=self.bb_std)
        if bbands is not None and not bbands.empty:
            try:
                df['bb_lower'] = bbands.iloc[:, 0]
                df['bb_middle'] = bbands.iloc[:, 1]
                df['bb_upper'] = bbands.iloc[:, 2]
                df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Error parsing Bollinger Bands: {e}")
                df['bb_upper'] = df['close']
                df['bb_middle'] = df['close']
                df['bb_lower'] = df['close']
                df['bb_width'] = 0
        
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=self.atr_period)
        
        adx_data = ta.adx(df['high'], df['low'], df['close'], length=self.adx_period)
        if adx_data is not None and not adx_data.empty:
            try:
                df['adx'] = adx_data.iloc[:, 0]
                df['dmp'] = adx_data.iloc[:, 1]
                df['dmn'] = adx_data.iloc[:, 2]
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Error parsing ADX: {e}")
                df['adx'] = 0
                df['dmp'] = 0
                df['dmn'] = 0
        
        df['obv'] = ta.obv(df['close'], df['volume'])
        
        df['volume_sma'] = ta.sma(df['volume'], length=20)
        if len(df) > 0:
            df['volume_ratio'] = df['volume'] / df['volume_sma']
        
        stoch_rsi = ta.stochrsi(df['close'], length=self.rsi_period)
        if stoch_rsi is not None and not stoch_rsi.empty:
            try:
                df['stoch_rsi_k'] = stoch_rsi.iloc[:, 0]
                df['stoch_rsi_d'] = stoch_rsi.iloc[:, 1]
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Error parsing Stochastic RSI: {e}")
                df['stoch_rsi_k'] = 50
                df['stoch_rsi_d'] = 50
        
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
