# ═══════════════════════════════════════════════════════
#  Telegram View Booster Bot - Configuration
# ═══════════════════════════════════════════════════════

# ── Bot Settings ──────────────────────────────────────
BOT_TOKEN = "8438741047:AAHbQM-gZm7yofdvZzQ4BTxCdNH-8p4ZLCs"  # Bot token from @BotFather
ADMIN_USER_ID = 8475718817
ADMIN_USERNAME = "@TB_RUMMAN_YT"

# ── SMM Panel ─────────────────────────────────────────
SMM_PANEL_API = "7f2a4780bedc1312745289830408d2ff"  # API key from easysmmpanel.com
SMM_PANEL_URL = "https://smmnea.com/api/v2"
SMM_SERVICE_ID = "4815"

# ── Bonus Settings ────────────────────────────────────
WELCOME_BONUS = 100
REF_BONUS = 500

# ── View Limits ───────────────────────────────────────
MIN_VIEW = 500
MAX_VIEW = 1000000

# ── Channels ──────────────────────────────────────────
REQUIRED_CHANNELS = ["@pythonViewbooster"]
PAYMENT_CHANNEL = "@pythonViewbooster"

# ── Payment Methods (Bangladesh) ──────────────────────
BKASH_NUMBER = "এই মুহূর্তে বিকাশের পেমেন্ট মেথডটি বন্ধ রয়েছে অতি শীঘ্রই অন করা হবে "       # আপনার bKash নম্বর
NAGAD_NUMBER = "01872109338"       # আপনার Nagad নম্বর
BINANCE_BEP20_ADDRESS = "0xe3473975d73e32e0bc0aa3b69aa4e76af67bf0d2"  # BEP20 (BSC) USDT address

# ── Deposit Packages ─────────────────────────────────
# price_bdt = bKash/Nagad price, price_usd = Binance USDT price
DEPOSIT_PACKAGES = [
    {"id": 1, "views": 75_000,    "price_bdt": 550,   "price_usd": 5,   "label": "📦 75K Views"},
    {"id": 2, "views": 170_000,   "price_bdt": 1100,  "price_usd": 10,  "label": "📦 170K Views"},
    {"id": 3, "views": 400_000,   "price_bdt": 2200,  "price_usd": 20,  "label": "📦 400K Views"},
    {"id": 4, "views": 750_000,   "price_bdt": 3300,  "price_usd": 30,  "label": "📦 750K Views"},
    {"id": 5, "views": 1_700_000, "price_bdt": 5500,  "price_usd": 50,  "label": "📦 1.7M Views"},
    {"id": 6, "views": 5_000_000, "price_bdt": 11000, "price_usd": 100, "label": "📦 5M Views"},
]

# ── Database ──────────────────────────────────────────
DATABASE_FILE = "bot_database.db"