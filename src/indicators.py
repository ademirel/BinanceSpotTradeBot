import pandas as pd
import pandas_ta as ta

class TechnicalIndicators:
    def __init__(self, config, logger=None):
        self.config = config
        self.logger = logger
        
        self.psar_acceleration = config.get('parabolic_sar.acceleration', 0.02)
        self.psar_maximum = config.get('parabolic_sar.maximum', 0.2)
        
        self.pivot_lookback = config.get('classic_pivot.lookback_candles', 5)
        self.pivot_tolerance = config.get('classic_pivot.tolerance_percent', 0.5)
    
    def calculate_indicators(self, klines):
        if not klines or len(klines) < 10:
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
        
        psar_data = ta.psar(
            df['high'], 
            df['low'], 
            df['close'],
            af0=self.psar_acceleration,
            af=self.psar_acceleration,
            max_af=self.psar_maximum
        )
        
        if psar_data is not None and not psar_data.empty:
            df['psar_long'] = psar_data['PSARl_' + str(self.psar_acceleration) + '_' + str(self.psar_maximum)]
            df['psar_short'] = psar_data['PSARs_' + str(self.psar_acceleration) + '_' + str(self.psar_maximum)]
            df['psar_af'] = psar_data['PSARaf_' + str(self.psar_acceleration) + '_' + str(self.psar_maximum)]
            df['psar_reverse'] = psar_data['PSARr_' + str(self.psar_acceleration) + '_' + str(self.psar_maximum)]
        else:
            df['psar_long'] = None
            df['psar_short'] = None
            df['psar_af'] = None
            df['psar_reverse'] = None
        
        return df.iloc[-1].to_dict()
    
    def calculate_classic_pivot(self, klines):
        """
        Calculate classic pivot points (P, S1, S2, S3, R1, R2, R3)
        Using the previous period's High, Low, Close
        """
        if not klines or len(klines) < 2:
            return None
        
        df = pd.DataFrame(klines, columns=[
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
    
    def check_s3_support_test(self, klines, current_price):
        """
        Check if price has tested S3 support without breaking it
        Returns: {
            'tested': bool,  # Has price approached S3?
            'broken': bool,  # Has price broken below S3?
            's3_level': float,
            'valid_entry': bool  # tested but not broken
        }
        """
        pivot_data = self.calculate_classic_pivot(klines)
        
        if not pivot_data:
            return {
                'tested': False,
                'broken': False,
                's3_level': None,
                'valid_entry': False
            }
        
        s3 = pivot_data['s3']
        
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        
        recent_candles = df.iloc[-self.pivot_lookback:]
        
        tolerance = s3 * (self.pivot_tolerance / 100)
        s3_upper_band = s3 + tolerance
        
        tested = False
        broken = False
        
        for _, candle in recent_candles.iterrows():
            candle_low = candle['low']
            
            if candle_low <= s3_upper_band:
                tested = True
            
            if candle_low < s3:
                broken = True
                break
        
        valid_entry = tested and not broken
        
        return {
            'tested': tested,
            'broken': broken,
            's3_level': s3,
            'valid_entry': valid_entry,
            'pivot_data': pivot_data
        }
