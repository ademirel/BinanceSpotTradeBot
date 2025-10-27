import pandas as pd
import pandas_ta as ta

class TechnicalIndicators:
    def __init__(self, config, logger=None):
        self.config = config
        self.logger = logger
        
        self.psar_acceleration = config.get('parabolic_sar.acceleration', 0.02)
        self.psar_maximum = config.get('parabolic_sar.maximum', 0.2)
    
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
