from datetime import datetime

import httpx

from config import (
    DS_GURUHLAR,
    DS_TALABALAR,
    DS_TOLOVLAR,
    DS_USTOZLAR,
    DS_YOZILISHLAR,
    NOTION_API_BASE,
    NOTION_TOKEN,
    NOTION_VERSION,
    TASHKENT_TZ,
)

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}


# ---------- Sana yordamchilari ----------

def bugun() -> str:
    """Asia/Tashkent bo'yicha bugungi sana, ISO (YYYY-MM-DD) formatda."""
    return datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d")


def sana_kk_oo_yyyy_dan(matn: str):
    """'25.08.2026' -> '2026-08-25'. Format noto'g'ri bo'lsa None qaytaradi."""
    try:
        kun, oy, yil = matn.strip().split(".")
        dt = datetime(int(yil), int(oy), int(kun))
        return dt.strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return None


def sana_ozbekcha(iso_sana: str) -> str:
    """'2026-08-25' -> '25.08.2026'"""
    dt = datetime.strptime(iso_sana, "%Y-%m-%d")
    return dt.strftime("%d.%m.%Y")


# ---------- Ichki yordamchilar ----------

async def _query(data_source_id: str, filter_obj=None, sorts=None) -> list[dict]:
    """Data source'ni to'liq (barcha sahifalar bilan) so'raydi."""
    url = f"{NOTION_API_BASE}/data_sources/{data_source_id}/query"
    natijalar: list[dict] = []
    body: dict = {}
    if filter_obj:
        body["filter"] = filter_obj
    if sorts:
        body["sorts"] = sorts

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            resp = await client.post(url, headers=HEADERS, json=body)
            resp.raise_for_status()
            data = resp.json()
            natijalar.extend(data.get("results", []))
            if data.get("has_more") and data.get("next_cursor"):
                body["start_cursor"] = data["next_cursor"]
            else:
                break
    return natijalar


def _title_matni(page: dict, prop_nomi: str) -> str:
    prop = page.get("properties", {}).get(prop_nomi, {})
    qismlar = prop.get("title", [])
    return "".join(q.get("plain_text", "") for q in qismlar) or "(nomsiz)"


async def _sahifa_yarat(data_source_id: str, properties: dict) -> str:
    body = {
        "parent": {"type": "data_source_id", "data_source_id": data_source_id},
        "properties": properties,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{NOTION_API_BASE}/pages", headers=HEADERS, json=body)
        resp.raise_for_status()
        return resp.json()["id"]


# ---------- O'qish (query) ----------

async def faol_ustozlar() -> list[dict]:
    """Holat = Faol bo'lgan ustozlar: [{'id', 'ism'}]"""
    filter_obj = {"property": "Holat", "status": {"equals": "Faol"}}
    sorts = [{"property": "Ism", "direction": "ascending"}]
    sahifalar = await _query(DS_USTOZLAR, filter_obj, sorts)
    return [{"id": p["id"], "ism": _title_matni(p, "Ism")} for p in sahifalar]


async def ustoz_faol_guruhlari(ustoz_id: str) -> list[dict]:
    """Berilgan ustozning Guruh holati = Faol bo'lgan guruhlari: [{'id', 'nomi'}]"""
    filter_obj = {
        "and": [
            {"property": "Ustoz", "relation": {"contains": ustoz_id}},
            {"property": "Guruh holati", "status": {"equals": "Faol"}},
        ]
    }
    sorts = [{"property": "Guruh nomi", "direction": "ascending"}]
    sahifalar = await _query(DS_GURUHLAR, filter_obj, sorts)
    return [{"id": p["id"], "nomi": _title_matni(p, "Guruh nomi")} for p in sahifalar]


async def talaba_qidirish(ism_qismi: str) -> list[dict]:
    """Ism bo'yicha qisman moslikda talabalarni qidiradi: [{'id', 'ism'}]"""
    filter_obj = {"property": "Ism", "title": {"contains": ism_qismi}}
    sorts = [{"property": "Ism", "direction": "ascending"}]
    sahifalar = await _query(DS_TALABALAR, filter_obj, sorts)
    return [{"id": p["id"], "ism": _title_matni(p, "Ism")} for p in sahifalar]


# ---------- Yozish (create) ----------

async def talaba_yaratish(ism: str, telegram_id) -> str:
    """Talabalar bazasiga yangi yozuv. page_id qaytaradi."""
    props: dict = {
        "Ism": {"title": [{"text": {"content": ism}}]},
        "Qo'shilgan sana": {"date": {"start": bugun()}},
    }
    if telegram_id:
        props["Telegram ID"] = {"rich_text": [{"text": {"content": str(telegram_id)}}]}
    return await _sahifa_yarat(DS_TALABALAR, props)


async def yozilish_yaratish(
    talaba_id: str, talaba_ism: str, guruh_id: str, guruh_nomi: str, boshlagan_sana: str
) -> str:
    """Yozilishlar bazasiga yozuv."""
    props = {
        "Nomi": {"title": [{"text": {"content": f"{talaba_ism} — {guruh_nomi}"}}]},
        "Talaba": {"relation": [{"id": talaba_id}]},
        "Guruh": {"relation": [{"id": guruh_id}]},
        "Holat": {"select": {"name": "O'qiyabdi"}},
        "Boshlagan sana": {"date": {"start": boshlagan_sana}},
    }
    return await _sahifa_yarat(DS_YOZILISHLAR, props)


async def tolov_yaratish(talaba_id: str, talaba_ism: str, summa: float) -> str:
    """To'lovlar bazasiga yozuv (sana — bugungi kun)."""
    sana = bugun()
    props = {
        "Nomi": {"title": [{"text": {"content": f"{talaba_ism} — {sana_ozbekcha(sana)}"}}]},
        "Talaba": {"relation": [{"id": talaba_id}]},
        "Summa": {"number": summa},
        "To'lov sanasi": {"date": {"start": sana}},
    }
    return await _sahifa_yarat(DS_TOLOVLAR, props)
