import asyncio
from datetime import datetime, timedelta

import httpx

from config import (
    DS_DARSLAR_GRAFIGI,
    DS_DAVOMAT,
    DS_GURUHLAR,
    DS_OYLIKLAR,
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


def kecha() -> str:
    """Asia/Tashkent bo'yicha kechagi sana, ISO (YYYY-MM-DD) formatda."""
    return (datetime.now(TASHKENT_TZ) - timedelta(days=1)).strftime("%Y-%m-%d")


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


# ---------- Ustozlar paneli: moliya, darslar, oyliklar ----------

async def ustoz_moliyaviy_malumot(ustoz_id: str) -> dict:
    """Ustoz sahifasidagi tayyor formula/rollup'larni o'qiydi: balans, ishlab topgan, olingan oyliklar."""
    sahifa = await _sahifa_olish(ustoz_id)
    props = sahifa.get("properties", {})

    balans = props.get("Ustoz balansi", {}).get("formula", {}).get("number")
    ishlab_topgani = props.get("Ishlab topgani", {}).get("rollup", {}).get("number")
    berilgan_oyliklar = props.get("Berilgan oyliklar", {}).get("rollup", {}).get("number")

    return {
        "balans": balans or 0,
        "ishlab_topgani": ishlab_topgani or 0,
        "berilgan_oyliklar": berilgan_oyliklar or 0,
    }


async def darslar_soni(guruh_idlari: list[str], holat: str) -> int:
    """Berilgan guruhlar ro'yxatida, belgilangan Holat'dagi darslar soni."""
    if not guruh_idlari:
        return 0
    or_filtri = [{"property": "Guruh", "relation": {"contains": gid}} for gid in guruh_idlari]
    filter_obj = {"and": [{"or": or_filtri}, {"property": "Holat", "select": {"equals": holat}}]}
    sahifalar = await _query(DS_DARSLAR_GRAFIGI, filter_obj)
    return len(sahifalar)


async def belgilanmagan_otgan_darslar(guruh_idlari: list[str]) -> list[dict]:
    """Muddati o'tgan (bugungacha), lekin hali Holat = 'Belgilanmagan' darslar."""
    if not guruh_idlari:
        return []
    or_filtri = [{"property": "Guruh", "relation": {"contains": gid}} for gid in guruh_idlari]
    filter_obj = {
        "and": [
            {"or": or_filtri},
            {"property": "Holat", "select": {"equals": "Belgilanmagan"}},
            {"property": "Rejadagi sana", "date": {"on_or_before": bugun()}},
        ]
    }
    sorts = [{"property": "Rejadagi sana", "direction": "ascending"}]
    sahifalar = await _query(DS_DARSLAR_GRAFIGI, filter_obj, sorts)

    natija = []
    for p in sahifalar:
        props = p.get("properties", {})
        sana_prop = props.get("Rejadagi sana", {}).get("date")
        sana = sana_prop["start"][:10] if sana_prop and sana_prop.get("start") else None
        dars_raqami = props.get("Dars raqami", {}).get("number")
        guruh_rel = props.get("Guruh", {}).get("relation", [])
        guruh_id = guruh_rel[0]["id"] if guruh_rel else None
        natija.append({"id": p["id"], "sana": sana, "dars_raqami": dars_raqami, "guruh_id": guruh_id})
    return natija


async def oylik_yaratish(ustoz_id: str, summa: float, sana: str) -> str:
    """Oyliklar bazasiga yozuv qo'shadi."""
    props = {
        "Nomi": {"title": [{"text": {"content": f"Oylik: {int(summa)} — {sana_ozbekcha(sana)}"}}]},
        "Ustoz": {"relation": [{"id": ustoz_id}]},
        "Summa": {"number": summa},
        "Sana": {"date": {"start": sana}},
    }
    return await _sahifa_yarat(DS_OYLIKLAR, props)


# ---------- "Ketma-ket kelmadi" tugmalari (Yozilish holatini o'zgartirish) ----------

class NotionXato(Exception):
    """Notion so'rovi muvaffaqiyatsiz bo'lganda, aniq xabar bilan."""

    def __init__(self, matn: str, status: int | None = None):
        super().__init__(matn)
        self.status = status


def _xato_matni(resp: httpx.Response) -> str:
    try:
        xabar = resp.json().get("message", resp.text)
    except Exception:
        xabar = resp.text
    return f"{resp.status_code}: {xabar}"[:500]


async def yozilishni_olish(page_id: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{NOTION_API_BASE}/pages/{page_id}", headers=HEADERS)
    if resp.status_code != 200:
        raise NotionXato(_xato_matni(resp), resp.status_code)
    return resp.json()


async def _sahifani_yangilash(page_id: str, properties: dict) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.patch(
            f"{NOTION_API_BASE}/pages/{page_id}", headers=HEADERS, json={"properties": properties}
        )
    if resp.status_code != 200:
        raise NotionXato(_xato_matni(resp), resp.status_code)


async def yozilishni_davom_ettirish(page_id: str) -> None:
    """Holat: Ta'tilda -> O'qiyabdi"""
    await _sahifani_yangilash(page_id, {"Holat": {"select": {"name": "O'qiyabdi"}}})


async def yozilishni_tugatish(page_id: str, sabab: str) -> None:
    """Holat -> Tugatdi, Tugagan sana = bugun (Toshkent), Izoh'ga sabab qo'shiladi."""
    sahifa = await yozilishni_olish(page_id)
    eski_izoh = _matn_xossasi(sahifa, "Izoh")
    sana = bugun()
    yangi_qator = f"Admin chiqardi ({sana}): {sabab}" if sabab else f"Admin chiqardi ({sana})"
    izoh = f"{eski_izoh}\n{yangi_qator}" if eski_izoh else yangi_qator
    if len(izoh) > 1900:
        izoh = izoh[-1900:]  # eng yangi yozuv saqlanib qoladi
    await _sahifani_yangilash(
        page_id,
        {
            "Holat": {"select": {"name": "Tugatdi"}},
            "Tugagan sana": {"date": {"start": sana}},
            "Izoh": {"rich_text": [{"text": {"content": izoh}}]},
        },
    )


# ---------- Talaba holati: yozilishlar, davomat, balans ----------

async def _query_limit(data_source_id: str, filter_obj=None, sorts=None, limit: int = 5) -> list[dict]:
    """Faqat birinchi `limit` ta natijani oladi (bitta so'rov)."""
    url = f"{NOTION_API_BASE}/data_sources/{data_source_id}/query"
    body: dict = {"page_size": limit}
    if filter_obj:
        body["filter"] = filter_obj
    if sorts:
        body["sorts"] = sorts
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers=HEADERS, json=body)
        resp.raise_for_status()
    return resp.json().get("results", [])


def _formula_qiymati(page: dict, prop_nomi: str):
    """Formula natijasini turidan qat'i nazar (number/string/boolean/date) qaytaradi."""
    prop = page.get("properties", {}).get(prop_nomi, {})
    formula = prop.get("formula") or {}
    qiymat = formula.get(formula.get("type"))
    if isinstance(qiymat, dict):  # date formulasi
        return qiymat.get("start")
    return qiymat


async def talaba_balansi(talaba_id: str) -> dict:
    """Talabalar bazasidagi tayyor formulalarni o'qiydi: Balans, Balans holati, Qarzga tushgan sana."""
    sahifa = await _sahifa_olish(talaba_id)
    qarz_sana = sahifa.get("properties", {}).get("Qarzga tushgan sana", {}).get("date")
    return {
        "balans": _formula_qiymati(sahifa, "Balans"),
        "balans_holati": _formula_qiymati(sahifa, "Balans holati"),
        "qarz_sana": qarz_sana["start"][:10] if qarz_sana and qarz_sana.get("start") else None,
    }


async def talaba_yozilishlari(talaba_id: str) -> list[dict]:
    """Talabaning barcha yozilishlari: [{'id', 'holat', 'guruh_id', 'guruh_nomi'}]"""
    filter_obj = {"property": "Talaba", "relation": {"contains": talaba_id}}
    sahifalar = await _query(DS_YOZILISHLAR, filter_obj)

    natija = []
    for p in sahifalar:
        props = p.get("properties", {})
        holat_prop = props.get("Holat", {}).get("select")
        guruh_rel = props.get("Guruh", {}).get("relation", [])
        natija.append(
            {
                "id": p["id"],
                "holat": holat_prop["name"] if holat_prop else None,
                "guruh_id": guruh_rel[0]["id"] if guruh_rel else None,
                "yozilish_nomi": _title_matni(p, "Nomi"),
            }
        )

    async def guruh_nomi(y: dict) -> str:
        if y["guruh_id"]:
            try:
                sahifa = await _sahifa_olish(y["guruh_id"])
                return _title_matni(sahifa, "Guruh nomi")
            except Exception:
                pass
        return y["yozilish_nomi"]

    nomlar = await asyncio.gather(*[guruh_nomi(y) for y in natija])
    for y, nomi in zip(natija, nomlar):
        y["guruh_nomi"] = nomi
    return natija


async def yozilish_davomati(yozilish_id: str, soni: int = 5) -> list[dict]:
    """Yozilish bo'yicha oxirgi `soni` ta davomat, yangisidan eskisiga: [{'sana', 'holat'}]"""
    filter_obj = {"property": "Yozilish", "relation": {"contains": yozilish_id}}
    sorts = [{"property": "Sana", "direction": "descending"}]
    sahifalar = await _query_limit(DS_DAVOMAT, filter_obj, sorts, soni)

    natija = []
    for p in sahifalar:
        props = p.get("properties", {})
        sana = props.get("Sana", {}).get("date")
        holat = props.get("Holat", {}).get("select")
        natija.append(
            {
                "sana": sana["start"][:10] if sana and sana.get("start") else None,
                "holat": holat["name"] if holat else None,
            }
        )
    return natija


async def yozilishni_tatilga_chiqarish(page_id: str) -> None:
    """Holat: O'qiyabdi -> Ta'tilda"""
    await _sahifani_yangilash(page_id, {"Holat": {"select": {"name": "Ta'tilda"}}})
