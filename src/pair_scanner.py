import time

class PairScanner:
    def __init__(self, binance_client, indicators_calc, config, logger=None):
        self.client = binance_client
        self.indicators = indicators_calc
        self.config = config
        self.logger = logger
        
        # Scanner settings
        self.pairs = config.get('scanner.pairs', [])
        self.scan_interval = config.get('scanner.scan_interval_seconds', 60)
        self.max_pairs_to_trade = config.get('scanner.max_pairs_to_trade', 5)
        
        # Timeframe
        self.timeframe = config.get('timeframe', '15m')
        
        # Cache for scan results
        self.last_scan_time = 0
        self.cached_results = []
    
    def scan_pairs(self, force_scan=False):
        """
        Scan all pairs and rank them by trend strength
        Returns list of pairs sorted by score (highest first)
        """
        # Check cache
        current_time = time.time()
        if not force_scan and (current_time - self.last_scan_time) < self.scan_interval:
            if self.logger:
                self.logger.debug(f"Using cached scan results ({len(self.cached_results)} pairs)")
            return self.cached_results
        
        if self.logger:
            self.logger.info(f"Scanning {len(self.pairs)} pairs for trading opportunities...")
        
        scored_pairs = []
        
        for symbol in self.pairs:
            try:
                # Get klines
                klines = self.client.get_klines(symbol, interval=self.timeframe, limit=100)
                
                if not klines:
                    continue
                
                # Calculate indicators
                indicators = self.indicators.calculate_indicators(klines)
                
                if not indicators:
                    continue
                
                # Calculate trend score
                score = self._calculate_trend_score(symbol, indicators)
                
                if score is not None and score > 0:
                    scored_pairs.append({
                        'symbol': symbol,
                        'score': score,
                        'indicators': indicators
                    })
                
                # Rate limiting
                time.sleep(0.1)
                
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error scanning {symbol}: {e}")
                continue
        
        # Sort by score (highest first)
        scored_pairs.sort(key=lambda x: x['score'], reverse=True)
        
        # Update cache
        self.cached_results = scored_pairs
        self.last_scan_time = current_time
        
        if self.logger:
            self.logger.info(f"Scan complete: {len(scored_pairs)} pairs with valid signals")
            if scored_pairs:
                top_5 = scored_pairs[:5]
                self.logger.info("Top 5 pairs:")
                for i, pair in enumerate(top_5, 1):
                    self.logger.info(f"  {i}. {pair['symbol']}: score={pair['score']:.2f}")
        
        return scored_pairs
    
    def _calculate_trend_score(self, symbol, indicators):
        """
        Calculate trend strength score for ranking pairs
        
        Score components:
        1. EMA trend (distance between fast and slow): 0-40 points
        2. RSI momentum: 0-30 points
        3. Heiken Ashi consistency: 0-20 points
        4. Volatility filter: 0-10 points
        
        Total: 0-100 points
        """
        try:
            score = 0
            
            # Component 1: EMA trend strength (0-40 points)
            ema_fast = indicators.get('ema_fast')
            ema_slow = indicators.get('ema_slow')
            
            if ema_fast and ema_slow and ema_fast > 0 and ema_slow > 0:
                # Calculate percentage distance
                ema_distance = ((ema_fast - ema_slow) / ema_slow) * 100
                
                # Positive distance = bullish, negative = bearish
                # Award points for strong trend (either direction)
                abs_distance = abs(ema_distance)
                
                # Scale: 0-5% distance → 0-40 points
                ema_score = min(abs_distance * 8, 40)
                score += ema_score
            
            # Component 2: RSI momentum (0-30 points)
            rsi = indicators.get('rsi')
            
            if rsi:
                # Award points for RSI extremes (either oversold or overbought)
                # Distance from midpoint (50)
                rsi_distance = abs(rsi - 50)
                
                # Scale: 0-50 distance → 0-30 points
                rsi_score = min(rsi_distance * 0.6, 30)
                score += rsi_score
            
            # Component 3: Heiken Ashi consistency (0-20 points)
            ha_bullish = indicators.get('ha_bullish', False)
            ha_bearish = indicators.get('ha_bearish', False)
            
            if ha_bullish or ha_bearish:
                score += 20
            
            # Component 4: Volatility filter (0-10 points)
            passes_volatility = indicators.get('passes_volatility_filter', False)
            
            if passes_volatility:
                score += 10
            else:
                # No volatility = significantly reduced score
                score *= 0.5
            
            return score
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error calculating score for {symbol}: {e}")
            return None
    
    def get_top_pairs(self, max_count=None):
        """
        Get top N pairs from last scan
        """
        if max_count is None:
            max_count = self.max_pairs_to_trade
        
        return self.cached_results[:max_count]
    
    def should_scan_symbol(self, symbol):
        """
        Check if symbol should be scanned (is in the pair list)
        """
        return symbol in self.pairs
    
    def get_pair_indicators(self, symbol):
        """
        Get cached indicators for a specific pair
        """
        for pair in self.cached_results:
            if pair['symbol'] == symbol:
                return pair.get('indicators')
        
        return None
