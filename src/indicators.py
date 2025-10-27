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
    
    def check_fibonacci_pivot_support(self, klines_1h, current_price, lookback_candles=5, tolerance_pct=0.5):
        """
        Fibonacci pivot support kontrolü:
        - Fiyat son N mum içinde pivot support seviyelerini (S1 veya S2) test etmiş mi?
        - Ama current fiyat hala support'un üzerinde mi? (kırmamış)
        
        Returns:
            dict: {
                'tested_support': bool,  # Support test edildi mi?
                'holding_support': bool,  # Support tutuyor mu?
                'pivot': float,
                's1': float,
                's2': float,
                'tested_level': str  # 'S1' veya 'S2' veya None
            }
        """
        if not klines_1h or len(klines_1h) < 2:
            return {
                'tested_support': False,
                'holding_support': False,
                'pivot': 0,
                's1': 0,
                's2': 0,
                'tested_level': None
            }
        
        df = pd.DataFrame(klines_1h, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        
        last_candle = df.iloc[-2]
        
        pivot = (last_candle['high'] + last_candle['low'] + last_candle['close']) / 3
        s1 = 2 * pivot - last_candle['high']
        s2 = pivot - (last_candle['high'] - last_candle['low'])
        r1 = 2 * pivot - last_candle['low']
        r2 = pivot + (last_candle['high'] - last_candle['low'])
        
        recent_candles = df.tail(lookback_candles)
        
        tested_s1 = False
        tested_s2 = False
        broken_s1 = False
        broken_s2 = False
        tested_level = None
        
        tolerance = tolerance_pct / 100.0
        
        for idx, candle in recent_candles.iterrows():
            candle_low = candle['low']
            candle_close = candle['close']
            
            if abs(candle_low - s1) / s1 <= tolerance and candle_low >= s1 * (1 - tolerance):
                tested_s1 = True
                tested_level = 'S1'
            
            if candle_close < s1 * (1 - tolerance) or candle_low < s1 * (1 - tolerance):
                broken_s1 = True
            
            if abs(candle_low - s2) / s2 <= tolerance and candle_low >= s2 * (1 - tolerance):
                tested_s2 = True
                if tested_level is None:
                    tested_level = 'S2'
            
            if candle_close < s2 * (1 - tolerance) or candle_low < s2 * (1 - tolerance):
                broken_s2 = True
        
        tested_support = tested_s1 or tested_s2
        
        holding_support = False
        if tested_support:
            if tested_s1 and not broken_s1 and current_price > s1:
                holding_support = True
            elif tested_s2 and not broken_s2 and current_price > s2:
                holding_support = True
        
        return {
            'tested_support': tested_support,
            'holding_support': holding_support,
            'pivot': pivot,
            's1': s1,
            's2': s2,
            'r1': r1,
            'r2': r2,
            'tested_level': tested_level
        }
