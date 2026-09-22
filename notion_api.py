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


async def _sahifa_olish(page_id: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{NOTION_API_BASE}/pages/{page_id}", headers=HEADERS)
        resp.raise_for_status()
        return resp.json()


async def guruh_linkini_olish(guruh_id: str) -> str:
    """Guruh sahifasidagi 'Guruh Link' matnini qaytaradi (bo'sh bo'lsa '')."""
    sahifa = await _sahifa_olish(guruh_id)
    return _matn_xossasi(sahifa, "Guruh Link")


async def telegram_id_boyicha_qidirish(telegram_id: str) -> list[dict]:
    """Telegram ID bo'yicha aniq moslikda talabalarni qidiradi: [{'id', 'ism'}]"""
    filter_obj = {"property": "Telegram ID", "rich_text": {"equals": str(telegram_id)}}
    sahifalar = await _query(DS_TALABALAR, filter_obj)
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


# ---------- Guruhlar hisoboti (faqat o'qish) ----------

def _matn_xossasi(page: dict, prop_nomi: str) -> str:
    prop = page.get("properties", {}).get(prop_nomi, {})
    qismlar = prop.get("rich_text", [])
    return "".join(q.get("plain_text", "") for q in qismlar)


def _guruh_malumotlari(page: dict) -> dict:
    props = page.get("properties", {})
    dars_kunlari = [o.get("name") for o in props.get("Dars kunlari", {}).get("multi_select", [])]
    dars_vaqti_prop = props.get("Dars vaqti", {}).get("select")
    dars_vaqti = dars_vaqti_prop["name"] if dars_vaqti_prop else None
    ustoz_rel = props.get("Ustoz", {}).get("relation", [])
    ustoz_id = ustoz_rel[0]["id"] if ustoz_rel else None
    oylik = props.get("Oylik to'lov", {}).get("number")
    return {
        "id": page["id"],
        "nomi": _title_matni(page, "Guruh nomi"),
        "dars_kunlari": dars_kunlari,
        "dars_vaqti": dars_vaqti,
        "ustoz_id": ustoz_id,
        "oylik_tolov": oylik,
        "link": _matn_xossasi(page, "Guruh Link"),
    }


async def kurs_boyicha_faol_guruhlar(kurs: str) -> list[dict]:
    """Berilgan Kurs bo'yicha Faol guruhlar, to'liq ma'lumot bilan."""
    filter_obj = {
        "and": [
            {"property": "Kurs", "select": {"equals": kurs}},
            {"property": "Guruh holati", "status": {"equals": "Faol"}},
        ]
    }
    sorts = [{"property": "Guruh nomi", "direction": "ascending"}]
    sahifalar = await _query(DS_GURUHLAR, filter_obj, sorts)
    return [_guruh_malumotlari(p) for p in sahifalar]


async def ustoz_faol_guruhlari_toliq(ustoz_id: str) -> list[dict]:
    """Berilgan ustozning Faol guruhlari, to'liq ma'lumot bilan."""
    filter_obj = {
        "and": [
            {"property": "Ustoz", "relation": {"contains": ustoz_id}},
            {"property": "Guruh holati", "status": {"equals": "Faol"}},
        ]
    }
    sorts = [{"property": "Guruh nomi", "direction": "ascending"}]
    sahifalar = await _query(DS_GURUHLAR, filter_obj, sorts)
    return [_guruh_malumotlari(p) for p in sahifalar]


async def barcha_ustozlar_lugati() -> dict:
    """id -> ism, ustoz holatidan qat'iy nazar (hisobotda ism ko'rsatish uchun)."""
    sahifalar = await _query(DS_USTOZLAR)
    return {p["id"]: _title_matni(p, "Ism") for p in sahifalar}


async def faol_yozilishlar_soni_guruh_boyicha() -> dict:
    """Har bir guruh uchun 'O'qiyabdi' holatidagi yozilishlar soni: {guruh_id: son}"""
    filter_obj = {"property": "Holat", "select": {"equals": "O'qiyabdi"}}
    sahifalar = await _query(DS_YOZILISHLAR, filter_obj)
    hisob: dict = {}
    for p in sahifalar:
        for rel in p.get("properties", {}).get("Guruh", {}).get("relation", []):
            gid = rel.get("id")
            if gid:
                hisob[gid] = hisob.get(gid, 0) + 1
    return hisob
