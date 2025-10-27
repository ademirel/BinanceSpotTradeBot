import pandas as pd
import pandas_ta as ta
import numpy as np

class TechnicalIndicators:
    def __init__(self, config, logger=None):
        self.config = config
        self.logger = logger
        
        self.stoch_rsi_period = config.get('indicators.stoch_rsi.period', 14)
        self.ma_short = config.get('indicators.moving_averages.short_period', 20)
        self.ma_long = config.get('indicators.moving_averages.long_period', 50)
        self.ema_fast = config.get('indicators.ema.fast_period', 12)
        self.ema_slow = config.get('indicators.ema.slow_period', 26)
        self.bb_period = config.get('indicators.bollinger.period', 20)
        self.bb_std = config.get('indicators.bollinger.std_dev', 2)
        self.atr_period = config.get('indicators.atr.period', 14)
        self.adx_period = config.get('indicators.adx.period', 14)
        self.ichimoku_tenkan = config.get('indicators.ichimoku.tenkan_period', 9)
        self.ichimoku_kijun = config.get('indicators.ichimoku.kijun_period', 26)
        self.ichimoku_senkou = config.get('indicators.ichimoku.senkou_period', 52)
    
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
        
        df['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
        df['ha_open'] = 0.0
        df.loc[0, 'ha_open'] = (df.loc[0, 'open'] + df.loc[0, 'close']) / 2
        for i in range(1, len(df)):
            df.loc[i, 'ha_open'] = (df.loc[i-1, 'ha_open'] + df.loc[i-1, 'ha_close']) / 2
        df['ha_high'] = df[['high', 'ha_open', 'ha_close']].max(axis=1)
        df['ha_low'] = df[['low', 'ha_open', 'ha_close']].min(axis=1)
        
        period_high_9 = df['high'].rolling(window=self.ichimoku_tenkan).max()
        period_low_9 = df['low'].rolling(window=self.ichimoku_tenkan).min()
        df['ichimoku_tenkan'] = (period_high_9 + period_low_9) / 2
        
        period_high_26 = df['high'].rolling(window=self.ichimoku_kijun).max()
        period_low_26 = df['low'].rolling(window=self.ichimoku_kijun).min()
        df['ichimoku_kijun'] = (period_high_26 + period_low_26) / 2
        
        df['ichimoku_senkou_a_calc'] = (df['ichimoku_tenkan'] + df['ichimoku_kijun']) / 2
        df['ichimoku_senkou_a'] = df['ichimoku_senkou_a_calc'].shift(-self.ichimoku_kijun)
        
        period_high_52 = df['high'].rolling(window=self.ichimoku_senkou).max()
        period_low_52 = df['low'].rolling(window=self.ichimoku_senkou).min()
        df['ichimoku_senkou_b_calc'] = (period_high_52 + period_low_52) / 2
        df['ichimoku_senkou_b'] = df['ichimoku_senkou_b_calc'].shift(-self.ichimoku_kijun)
        
        if len(df) > self.ichimoku_kijun:
            current_senkou_a = df['ichimoku_senkou_a_calc'].iloc[-self.ichimoku_kijun]
            current_senkou_b = df['ichimoku_senkou_b_calc'].iloc[-self.ichimoku_kijun]
            df.loc[df.index[-1], 'ichimoku_senkou_a'] = current_senkou_a
            df.loc[df.index[-1], 'ichimoku_senkou_b'] = current_senkou_b
        
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
        
        stoch_rsi = ta.stochrsi(df['close'], length=self.stoch_rsi_period)
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
