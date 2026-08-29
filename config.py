import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()  # lokal ishlash uchun .env fayldan o'qiydi, Railway'da ENV'dan oladi

BOT_TOKEN = os.environ["BOT_TOKEN"]
NOTION_TOKEN = os.environ["NOTION_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])

TASHKENT_TZ = ZoneInfo("Asia/Tashkent")

NOTION_VERSION = "2025-09-03"
NOTION_API_BASE = "https://api.notion.com/v1"

# Notion data source ID'lari
DS_USTOZLAR = "952ac188-93a2-433a-98bd-628028b69e23"
DS_GURUHLAR = "1fa6f318-9629-4970-a2fd-4e133c02a204"
DS_TALABALAR = "d9ce3228-ad86-49ed-b2fb-61319165eb82"
DS_YOZILISHLAR = "83a9b84e-2ef0-4d9f-906e-a7584b702d4e"
DS_TOLOVLAR = "cf832f9b-0b30-430f-bc6a-7ca6c3f3bc02"

SAHIFA_HAJMI = 10  # raqamli tugmalar ro'yxatidagi elementlar soni
