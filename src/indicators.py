import pandas as pd
import pandas_ta as ta

class TechnicalIndicators:
    def __init__(self, config, logger=None):
        self.config = config
        self.logger = logger
        
        self.ma_fast = config.get('moving_averages.fast', 9)
        self.ma_medium = config.get('moving_averages.medium', 21)
        self.ma_slow = config.get('moving_averages.slow', 49)
        
        self.pivot_lookback = config.get('daily_pivot.lookback_candles', 20)
        self.pivot_tolerance = config.get('daily_pivot.tolerance_percent', 0.5)
    
    def calculate_indicators(self, klines):
        """
        Calculate Moving Averages (9, 21, 49) on 15m timeframe
        Check if crossovers happened in last 3 candles (45 minutes)
        """
        if not klines or len(klines) < self.ma_slow + 5:
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
        
        df['ma_fast'] = ta.sma(df['close'], length=self.ma_fast)
        df['ma_medium'] = ta.sma(df['close'], length=self.ma_medium)
        df['ma_slow'] = ta.sma(df['close'], length=self.ma_slow)
        
        latest = df.iloc[-1]
        
        result = latest.to_dict()
        
        result['ma_fast_crossed_slow'] = False
        result['ma_medium_crossed_slow'] = False
        
        crossover_window = 3
        
        for i in range(1, min(crossover_window + 1, len(df))):
            current = df.iloc[-i]
            previous = df.iloc[-(i+1)] if i+1 <= len(df) else None
            
            if previous is not None:
                if not pd.isna(current['ma_fast']) and not pd.isna(current['ma_slow']):
                    if not pd.isna(previous['ma_fast']) and not pd.isna(previous['ma_slow']):
                        if previous['ma_fast'] <= previous['ma_slow'] and current['ma_fast'] > current['ma_slow']:
                            result['ma_fast_crossed_slow'] = True
                
                if not pd.isna(current['ma_medium']) and not pd.isna(current['ma_slow']):
                    if not pd.isna(previous['ma_medium']) and not pd.isna(previous['ma_slow']):
                        if previous['ma_medium'] <= previous['ma_slow'] and current['ma_medium'] > current['ma_slow']:
                            result['ma_medium_crossed_slow'] = True
        
        result['ma_fast_above_slow'] = not pd.isna(latest['ma_fast']) and not pd.isna(latest['ma_slow']) and latest['ma_fast'] > latest['ma_slow']
        result['ma_medium_above_slow'] = not pd.isna(latest['ma_medium']) and not pd.isna(latest['ma_slow']) and latest['ma_medium'] > latest['ma_slow']
        
        return result
    
    def calculate_daily_pivot(self, daily_klines):
        """
        Calculate daily pivot points (P, S1, S2, S3, R1, R2, R3)
        Using the previous day's High, Low, Close
        """
        if not daily_klines or len(daily_klines) < 2:
            return None
        
        df = pd.DataFrame(daily_klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        
        prev_high = df['high'].iloc[-2]
        prev_low = df['low'].iloc[-2]
        prev_close = df['close'].iloc[-2]
        
        pivot = (prev_high + prev_low + prev_close) / 3
        
        s1 = (2 * pivot) - prev_high
        s2 = pivot - (prev_high - prev_low)
        s3 = prev_low - 2 * (prev_high - pivot)
        
        r1 = (2 * pivot) - prev_low
        r2 = pivot + (prev_high - prev_low)
        r3 = prev_high + 2 * (pivot - prev_low)
        
        return {
            'pivot': pivot,
            's1': s1,
            's2': s2,
            's3': s3,
            'r1': r1,
            'r2': r2,
            'r3': r3
        }
    
    def check_daily_pivot_test(self, klines_15m, daily_klines, current_price):
        """
        Check if price has tested daily pivot without breaking it
        Returns: {
            'tested': bool,  # Has price approached pivot?
            'broken': bool,  # Has price broken below pivot?
            'pivot_level': float,
            'valid_entry': bool  # tested but not broken
        }
        """
        pivot_data = self.calculate_daily_pivot(daily_klines)
        
        if not pivot_data:
            return {
                'tested': False,
                'broken': False,
                'pivot_level': None,
                'valid_entry': False
            }
        
        pivot = pivot_data['pivot']
        
        df = pd.DataFrame(klines_15m, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        
        recent_candles = df.iloc[-self.pivot_lookback:]
        
        tolerance = pivot * (self.pivot_tolerance / 100)
        pivot_lower_band = pivot - tolerance
        pivot_upper_band = pivot + tolerance
        
        tested = False
        broken = False
        
        for _, candle in recent_candles.iterrows():
            candle_low = candle['low']
            candle_close = candle['close']
            
            if pivot_lower_band <= candle_low <= pivot_upper_band:
                tested = True
            
            if candle_close < pivot_lower_band:
                broken = True
                break
        
        valid_entry = tested and not broken
        
        return {
            'tested': tested,
            'broken': broken,
            'pivot_level': pivot,
            'valid_entry': valid_entry,
            'pivot_data': pivot_data
        }
