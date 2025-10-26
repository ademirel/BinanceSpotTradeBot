import pandas as pd

class SignalGenerator:
    def __init__(self, config, logger=None):
        self.config = config
        self.logger = logger
        
        self.rsi_buy = config.get('signal_thresholds.rsi_buy_threshold', 35)
        self.rsi_sell = config.get('signal_thresholds.rsi_sell_threshold', 65)
        self.macd_strength = config.get('signal_thresholds.macd_signal_strength', 0.0001)
        self.volume_spike_threshold = config.get('signal_thresholds.volume_spike', 1.5)
        self.adx_strong_trend = config.get('signal_thresholds.adx_strong_trend', 25)
        self.bb_squeeze_threshold = config.get('signal_thresholds.bb_squeeze', 0.02)
    
    def generate_signal(self, indicators):
        if not indicators or 'rsi' not in indicators:
            return 'HOLD'
        
        rsi = indicators.get('rsi', 50)
        macd = indicators.get('macd', 0)
        macd_signal = indicators.get('macd_signal', 0)
        macd_hist = indicators.get('macd_hist', 0)
        
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
        
        obv = indicators.get('obv', 0)
        atr = indicators.get('atr', 0)
        
        if pd.isna(rsi) or pd.isna(current_price):
            return 'HOLD'
        
        indicators_fired = {'buy': [], 'sell': []}
        
        if not pd.isna(rsi):
            if rsi < self.rsi_buy:
                indicators_fired['buy'].append('rsi')
            elif rsi > self.rsi_sell:
                indicators_fired['sell'].append('rsi')
        
        if not pd.isna(stoch_rsi_k) and not pd.isna(stoch_rsi_d):
            if stoch_rsi_k < 20 and stoch_rsi_k > stoch_rsi_d:
                indicators_fired['buy'].append('stoch_rsi')
            elif stoch_rsi_k > 80 and stoch_rsi_k < stoch_rsi_d:
                indicators_fired['sell'].append('stoch_rsi')
        
        if not pd.isna(macd) and not pd.isna(macd_signal) and not pd.isna(macd_hist):
            if macd > macd_signal and macd_hist > self.macd_strength:
                indicators_fired['buy'].append('macd')
            elif macd < macd_signal and macd_hist < -self.macd_strength:
                indicators_fired['sell'].append('macd')
        
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
        
        if not pd.isna(volume_ratio) and volume_ratio > self.volume_spike_threshold:
            if len(indicators_fired['buy']) > len(indicators_fired['sell']):
                indicators_fired['buy'].append('volume')
            elif len(indicators_fired['sell']) > len(indicators_fired['buy']):
                indicators_fired['sell'].append('volume')
        
        if not pd.isna(atr) and atr > 0:
            price_volatility_pct = (atr / current_price) * 100 if current_price > 0 else 0
            if price_volatility_pct > 2.0:
                if len(indicators_fired['buy']) > len(indicators_fired['sell']):
                    indicators_fired['buy'].append('atr')
                elif len(indicators_fired['sell']) > len(indicators_fired['buy']):
                    indicators_fired['sell'].append('atr')
        
        buy_count = len(indicators_fired['buy'])
        sell_count = len(indicators_fired['sell'])
        
        required_signals = 4
        
        if buy_count >= required_signals:
            return 'BUY'
        elif sell_count >= required_signals:
            return 'SELL'
        else:
            return 'HOLD'
