# Target coins for arbitrage monitoring
TARGET_COINS = ['BTC', 'ETH', 'XRP', 'SOL', 'ADA', 'DOGE', 'LINK', 'DOT', 'AVAX', 'POL']

# Polling interval in seconds
POLLING_INTERVAL = 3

# Database path
DB_PATH = 'data/arbitrage.db'

# Exchange fee rates (trading)
UPBIT_FEE = 0.0005    # 0.05%
BINANCE_FEE = 0.001   # 0.10%

# Bridge coins for implied KRW/USDT exchange rate
# These coins have fast, cheap transfers between exchanges
BRIDGE_COINS = ['XRP', 'XLM']

# Withdrawal fees (in coin units, approximate)
WITHDRAWAL_FEES = {
    'XRP': 1.0,      # Binance XRP withdrawal
    'XLM': 0.1,      # Binance XLM withdrawal
}

# Data staleness threshold in seconds
DATA_STALE_THRESHOLD = 15

# Retry configuration
RETRY_DELAY = 10     # seconds between retries
MAX_RETRIES = 3
BACKOFF_DELAY = 60   # seconds after max retries exceeded

# Exchange-specific symbol lists
UPBIT_SYMBOLS = [f"{coin}/KRW" for coin in TARGET_COINS]
BINANCE_SYMBOLS = [f"{coin}/USDT" for coin in TARGET_COINS]

# Data retention
RETENTION_DAYS_TICKERS = 7
RETENTION_DAYS_OPPORTUNITIES = 30

# Cleanup interval in seconds (24 hours)
CLEANUP_INTERVAL = 24 * 60 * 60
