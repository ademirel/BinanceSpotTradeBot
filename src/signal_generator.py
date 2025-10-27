import pandas as pd

class SignalGenerator:
    def __init__(self, config, logger=None):
        self.config = config
        self.logger = logger
        
        self.volume_spike_threshold = config.get('signal_thresholds.volume_spike', 1.5)
        self.adx_strong_trend = config.get('signal_thresholds.adx_strong_trend', 25)
        self.bb_squeeze_threshold = config.get('signal_thresholds.bb_squeeze', 0.02)
    
    def generate_signal(self, indicators):
        if not indicators or 'close' not in indicators:
            return 'HOLD'
        
        ema_fast = indicators.get('ema_fast', 0)
        ema_slow = indicators.get('ema_slow', 0)
        current_price = indicators.get('close', 0)
        
        bb_upper = indicators.get('bb_upper', 0)
        bb_lower = indicators.get('bb_lower', 0)
        bb_middle = indicators.get('bb_middle', 0)
        bb_width = indicators.get('bb_width', 0)
        
        adx = indicators.get('adx', 0)
        dmp = indicators.get('dmp', 0)
        dmn = indicators.get('dmn', 0)
        
        volume_ratio = indicators.get('volume_ratio', 1.0)
        stoch_rsi_k = indicators.get('stoch_rsi_k', 50)
        stoch_rsi_d = indicators.get('stoch_rsi_d', 50)
        
        ha_open = indicators.get('ha_open', 0)
        ha_close = indicators.get('ha_close', 0)
        ha_high = indicators.get('ha_high', 0)
        ha_low = indicators.get('ha_low', 0)
        
        ichimoku_tenkan = indicators.get('ichimoku_tenkan', 0)
        ichimoku_kijun = indicators.get('ichimoku_kijun', 0)
        ichimoku_senkou_a = indicators.get('ichimoku_senkou_a', 0)
        ichimoku_senkou_b = indicators.get('ichimoku_senkou_b', 0)
        
        obv = indicators.get('obv', 0)
        atr = indicators.get('atr', 0)
        
        if pd.isna(current_price):
            return 'HOLD'
        
        indicators_fired = {'buy': [], 'sell': []}
        
        ha_bullish = False
        ha_bearish = False
        if not pd.isna(ha_open) and not pd.isna(ha_close):
            ha_bullish = ha_close > ha_open
            ha_bearish = ha_close < ha_open
        
        ichimoku_above_cloud = False
        ichimoku_below_cloud = False
        if not pd.isna(ichimoku_tenkan) and not pd.isna(ichimoku_kijun) and not pd.isna(ichimoku_senkou_a) and not pd.isna(ichimoku_senkou_b):
            cloud_top = max(ichimoku_senkou_a, ichimoku_senkou_b)
            cloud_bottom = min(ichimoku_senkou_a, ichimoku_senkou_b)
            
            if current_price > cloud_top and ichimoku_tenkan > ichimoku_kijun:
                ichimoku_above_cloud = True
            elif current_price < cloud_bottom and ichimoku_tenkan < ichimoku_kijun:
                ichimoku_below_cloud = True
        
        if ha_bullish and ichimoku_above_cloud:
            indicators_fired['buy'].append('heiken_ashi')
            indicators_fired['buy'].append('ichimoku')
        elif ha_bearish and ichimoku_below_cloud:
            indicators_fired['sell'].append('heiken_ashi')
            indicators_fired['sell'].append('ichimoku')
        
        if not pd.isna(stoch_rsi_k) and not pd.isna(stoch_rsi_d):
            if stoch_rsi_k < 20 and stoch_rsi_k > stoch_rsi_d:
                indicators_fired['buy'].append('stoch_rsi')
            elif stoch_rsi_k > 80 and stoch_rsi_k < stoch_rsi_d:
                indicators_fired['sell'].append('stoch_rsi')
        
        if not pd.isna(ema_fast) and not pd.isna(ema_slow):
            if ema_fast > ema_slow and current_price > ema_fast:
                indicators_fired['buy'].append('ema')
            elif ema_fast < ema_slow and current_price < ema_fast:
                indicators_fired['sell'].append('ema')
        
        if not pd.isna(adx) and not pd.isna(dmp) and not pd.isna(dmn):
            if adx > self.adx_strong_trend:
                if dmp > dmn:
                    indicators_fired['buy'].append('adx')
                elif dmn > dmp:
                    indicators_fired['sell'].append('adx')
        
        if not pd.isna(bb_upper) and not pd.isna(bb_lower) and not pd.isna(bb_middle):
            bb_signal = False
            if current_price <= bb_lower:
                indicators_fired['buy'].append('bb')
                bb_signal = True
            elif current_price >= bb_upper:
                indicators_fired['sell'].append('bb')
                bb_signal = True
            
            if not bb_signal and not pd.isna(bb_width) and bb_width < self.bb_squeeze_threshold:
                if current_price > bb_middle:
                    indicators_fired['buy'].append('bb_squeeze')
                elif current_price < bb_middle:
                    indicators_fired['sell'].append('bb_squeeze')
        
        
        buy_count = len(indicators_fired['buy'])
        sell_count = len(indicators_fired['sell'])
        
        required_signals = 4
        
        if buy_count >= required_signals:
            return 'BUY'
        elif sell_count >= required_signals:
            return 'SELL'
        else:
            return 'HOLD'
