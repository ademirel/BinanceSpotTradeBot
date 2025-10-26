class SignalGenerator:
    def __init__(self, config, logger=None):
        self.config = config
        self.logger = logger
        
        self.rsi_buy = config.get('signal_thresholds.rsi_buy_threshold', 35)
        self.rsi_sell = config.get('signal_thresholds.rsi_sell_threshold', 65)
        self.macd_strength = config.get('signal_thresholds.macd_signal_strength', 0.0001)
    
    def generate_signal(self, indicators):
        if not indicators or 'rsi' not in indicators:
            return 'HOLD'
        
        rsi = indicators.get('rsi')
        macd = indicators.get('macd', 0)
        macd_signal = indicators.get('macd_signal', 0)
        macd_hist = indicators.get('macd_hist', 0)
        sma_short = indicators.get('sma_short', 0)
        sma_long = indicators.get('sma_long', 0)
        current_price = indicators.get('close', 0)
        
        if pd.isna(rsi) or pd.isna(macd) or pd.isna(sma_short) or pd.isna(sma_long):
            return 'HOLD'
        
        buy_signals = 0
        sell_signals = 0
        
        if rsi < self.rsi_buy:
            buy_signals += 1
        elif rsi > self.rsi_sell:
            sell_signals += 1
        
        if macd > macd_signal and macd_hist > self.macd_strength:
            buy_signals += 1
        elif macd < macd_signal and macd_hist < -self.macd_strength:
            sell_signals += 1
        
        if sma_short > sma_long and current_price > sma_short:
            buy_signals += 1
        elif sma_short < sma_long and current_price < sma_short:
            sell_signals += 1
        
        if buy_signals >= 2:
            return 'BUY'
        elif sell_signals >= 2:
            return 'SELL'
        else:
            return 'HOLD'

import pandas as pd
