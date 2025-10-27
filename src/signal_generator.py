import pandas as pd

class SignalGenerator:
    def __init__(self, config, logger=None):
        self.config = config
        self.logger = logger
    
    def generate_signal(self, indicators):
        if not indicators or 'close' not in indicators:
            return 'HOLD'
        
        current_price = indicators.get('close', 0)
        psar_long = indicators.get('psar_long')
        psar_short = indicators.get('psar_short')
        
        if pd.isna(current_price) or current_price == 0:
            return 'HOLD'
        
        if not pd.isna(psar_long):
            return 'BUY'
        elif not pd.isna(psar_short):
            return 'SELL'
        else:
            return 'HOLD'
