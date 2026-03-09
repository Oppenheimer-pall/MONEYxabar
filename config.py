"""
⚙️ Konfiguratsiya — environment variables orqali
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ══════════════════════════════════════════
#  ASOSIY SOZLAMALAR
# ══════════════════════════════════════════

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN environment variable topilmadi!")

ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_RAW.split(",") if x.strip().isdigit()]

# ══════════════════════════════════════════
#  TO'LOV SOZLAMALARI
# ══════════════════════════════════════════

FEE_RATE_LOCAL         = float(os.getenv("FEE_RATE_LOCAL", "0.003"))
FEE_RATE_INTERNATIONAL = float(os.getenv("FEE_RATE_INTERNATIONAL", "0.005"))

MIN_FEE_LOCAL          = float(os.getenv("MIN_FEE_LOCAL", "300"))
MAX_FEE_LOCAL          = float(os.getenv("MAX_FEE_LOCAL", "3000"))
MIN_FEE_INTERNATIONAL  = float(os.getenv("MIN_FEE_INTERNATIONAL", "500"))
MAX_FEE_INTERNATIONAL  = float(os.getenv("MAX_FEE_INTERNATIONAL", "5000"))

MIN_TRANSFER           = float(os.getenv("MIN_TRANSFER", "1000"))
MAX_TRANSFER           = float(os.getenv("MAX_TRANSFER", "50000000"))
MAX_DAILY_TRANSFER     = float(os.getenv("MAX_DAILY_TRANSFER", "100000000"))

# ══════════════════════════════════════════
#  DATABASE
# ══════════════════════════════════════════

# Railway'da /data/ volume ishlatiladi, lokalda ./card_bot.db
DB_PATH = os.getenv("DB_PATH", "/data/card_bot.db")

# ══════════════════════════════════════════
#  LOG
# ══════════════════════════════════════════

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
