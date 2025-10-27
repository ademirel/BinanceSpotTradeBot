import pandas as pd

class SignalGenerator:
    def __init__(self, config, logger=None):
        self.config = config
        self.logger = logger
    
    def generate_signal(self, indicators):
        """
        Generate BUY/SELL/HOLD signal based on MA crossovers
        BUY: MA9 and MA21 both crossed MA49 from below to above
        SELL: Currently not used (only close positions based on stop loss / trailing stop)
        """
        if not indicators or 'close' not in indicators:
            return 'HOLD'
        
        current_price = indicators.get('close', 0)
        
        if pd.isna(current_price) or current_price == 0:
            return 'HOLD'
        
        ma_fast = indicators.get('ma_fast')
        ma_medium = indicators.get('ma_medium')
        ma_slow = indicators.get('ma_slow')
        
        ma_fast_crossed_slow = indicators.get('ma_fast_crossed_slow', False)
        ma_medium_crossed_slow = indicators.get('ma_medium_crossed_slow', False)
        ma_fast_above_slow = indicators.get('ma_fast_above_slow', False)
        ma_medium_above_slow = indicators.get('ma_medium_above_slow', False)
        
        if pd.isna(ma_fast) or pd.isna(ma_medium) or pd.isna(ma_slow):
            return 'HOLD'
        
        if ma_fast_crossed_slow and ma_medium_crossed_slow and ma_fast_above_slow and ma_medium_above_slow:
            return 'BUY'
        
        return 'HOLD'
