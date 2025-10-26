import yaml
import os
from dotenv import load_dotenv

class ConfigLoader:
    def __init__(self, config_file='config.yaml'):
        load_dotenv()
        
        with open(config_file, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.api_key = os.getenv('BINANCE_API_KEY')
        self.api_secret = os.getenv('BINANCE_API_SECRET')
        self.testnet = os.getenv('BINANCE_TESTNET', 'false').lower() == 'true'
        
    def get(self, key, default=None):
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return value
    
    @property
    def top_coins_count(self):
        return self.get('top_coins_count', 20)
    
    @property
    def position_size_usd(self):
        return self.get('position_size_usd', 100.0)
    
    @property
    def stop_loss_percent(self):
        return self.get('stop_loss_percent', 2.0)
    
    @property
    def trailing_stop_percent(self):
        return self.get('trailing_stop_percent', 1.5)
    
    @property
    def check_interval(self):
        return self.get('check_interval_seconds', 60)
    
    @property
    def max_open_positions(self):
        return self.get('max_open_positions', 20)
