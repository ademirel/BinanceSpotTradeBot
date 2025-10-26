# Binance Trading Bot

Binance spot piyasasında işlem hacmine göre top 20 coin ile otomatik trading yapan Python bot. Momentum tabanlı strateji kullanarak limit emirler açar ve trailing stop mekanizması ile karları maksimize eder.

## Özellikler

- **Otomatik Coin Seçimi**: 24 saatlik işlem hacmine göre top N coin'i otomatik belirler
- **Multi-Pair Trading**: Birden fazla coin için eşzamanlı işlem yönetimi
- **Momentum Stratejisi**: RSI, MACD ve Moving Average göstergeleri ile sinyal üretimi
- **Limit Emirler**: Daha iyi fiyattan giriş için limit emirler kullanır
- **Trailing Stop**: Trend devam ederken karı kilitler
- **Stop-Loss**: Her pozisyon için otomatik risk yönetimi
- **Detaylı Loglama**: Tüm işlemler, sinyaller ve pozisyon değişiklikleri log dosyasına kaydedilir

## Kurulum

### 1. Binance API Key Oluşturma

1. [Binance](https://www.binance.com)'e giriş yapın
2. Hesap > API Management bölümüne gidin
3. Yeni bir API Key oluşturun
4. **Önemli**: Spot Trading iznini aktifleştirin
5. API Key ve Secret Key'i kaydedin

### 2. Konfigürasyon

`.env.example` dosyasını `.env` olarak kopyalayın:

```bash
cp .env.example .env
```

`.env` dosyasını düzenleyerek API key'lerinizi ekleyin:

```
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
```

### 3. Parametreleri Ayarlama

`config.yaml` dosyasını düzenleyerek trading parametrelerini ayarlayabilirsiniz:

```yaml
# Kaç coin ile işlem yapılacak
top_coins_count: 20

# Her coin için pozisyon büyüklüğü (USD)
position_size_usd: 100.0

# Stop loss yüzdesi
stop_loss_percent: 2.0

# Trailing stop yüzdesi
trailing_stop_percent: 1.5

# Kontrol aralığı (saniye)
check_interval_seconds: 60

# Maksimum açık pozisyon sayısı
max_open_positions: 20
```

## Kullanım

Bot'u başlatmak için:

```bash
python main.py
```

Bot durdurmak için `Ctrl+C` tuşlarına basın.

## Log Dosyaları

Bot tüm işlemleri log dosyalarına kaydeder:

- **Trading Logs**: `logs/trading_bot_YYYYMMDD.log` - Tüm bot aktiviteleri
- **Trade History**: `logs/trade_history.log` - Kapanan pozisyonların detayları
- **Positions**: `positions.json` - Açık pozisyonlar (bot yeniden başlatıldığında devam eder)

## Strateji Nasıl Çalışır?

### Sinyal Üretimi

Bot her coin için aşağıdaki göstergeleri hesaplar ve analiz eder:

1. **RSI (Relative Strength Index)**: Aşırı alım/satım seviyelerini tespit eder
2. **MACD (Moving Average Convergence Divergence)**: Trend yönünü belirler
3. **Moving Averages**: 20 ve 50 periyotluk hareketli ortalamalar ile trend onayı

**ALIM Sinyali**: En az 2 gösterge alım yönünde olduğunda
**SATIM Sinyali**: En az 2 gösterge satım yönünde olduğunda

### Risk Yönetimi

- **Limit Emirler**: Mevcut fiyattan %0.2 daha düşük fiyattan limit emir açar
- **Stop-Loss**: Giriş fiyatından %2 (varsayılan) zarar durumunda otomatik kapanır
- **Trailing Stop**: Pozisyon kâra geçtiğinde aktif olur ve fiyat en yüksek seviyeden %1.5 (varsayılan) geri çekildiğinde kapanır

## Önemli Uyarılar

⚠️ **Risk Uyarısı**: 
- Bu bot gerçek para ile işlem yapar!
- Küçük miktarlarla test edin
- Kayıplarınızı karşılayabileceğiniz miktarlarla işlem yapın
- Bot piyasa koşullarına bağlı olarak zarar edebilir

⚠️ **Güvenlik**:
- API key'lerinizi asla paylaşmayın
- `.env` dosyasını asla git'e eklemeyin
- API key'e sadece Spot Trading iznini verin
- Withdrawal (Para Çekme) iznini vermeyin

⚠️ **Test Ortamı**:
- İlk olarak Binance Testnet'te test etmeniz önerilir
- Testnet için: `.env` dosyasında `BINANCE_TESTNET=true` yapın

## Sorun Giderme

### "Insufficient balance" hatası
- USDT bakiyenizi kontrol edin
- `position_size_usd` değerini azaltın

### "Invalid symbol" hatası
- Bazı coinler trading için uygun olmayabilir
- Bot otomatik olarak bu coinleri atlayacaktır

### API rate limit hatası
- `check_interval_seconds` değerini artırın
- `top_coins_count` değerini azaltın

## Lisans

Bu proje eğitim amaçlıdır. Kullanımdan doğacak kayıplardan yazılım sorumlu değildir.
