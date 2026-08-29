from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from config import SAHIFA_HAJMI

BEKOR_TUGMASI = InlineKeyboardButton(text="❌ Bekor qilish", callback_data="bekor")
ORQAGA_TUGMASI = InlineKeyboardButton(text="⬅️ Orqaga", callback_data="orqaga")

YANGI_TALABA_MATNI = "➕ Yangi talaba"


def asosiy_pastki_klaviatura() -> ReplyKeyboardMarkup:
    """Xabar yozish maydoni ustida doimiy turadigan tugma."""
    kb = ReplyKeyboardBuilder()
    kb.button(text=YANGI_TALABA_MATNI)
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)


def turi_tanlash_klaviaturasi() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🆕 Yangi talaba", callback_data="turi:yangi")
    kb.button(text="🔁 Mavjud talaba", callback_data="turi:mavjud")
    kb.adjust(1)
    kb.row(BEKOR_TUGMASI)
    return kb.as_markup()


def matn_kiritish_klaviaturasi() -> InlineKeyboardMarkup:
    """Faqat matn kiritiladigan qadamlar uchun (Ism, Qidiruv)."""
    kb = InlineKeyboardBuilder()
    kb.row(ORQAGA_TUGMASI, BEKOR_TUGMASI)
    return kb.as_markup()


def tgid_klaviaturasi() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⏭️ O'tkazib yuborish", callback_data="tgid:otkazish")
    kb.adjust(1)
    kb.row(ORQAGA_TUGMASI, BEKOR_TUGMASI)
    return kb.as_markup()


def raqamli_royxat_matni(sarlavha: str, royxat: list[dict], nomi_kaliti: str, sahifa: int) -> str:
    boshlanish = sahifa * SAHIFA_HAJMI
    tugash = boshlanish + SAHIFA_HAJMI
    qatorlar = [sarlavha, ""]
    for i, element in enumerate(royxat[boshlanish:tugash], start=1):
        qatorlar.append(f"{i}. {element[nomi_kaliti]}")
    return "\n".join(qatorlar)


def raqamli_royxat_klaviaturasi(
    royxat: list[dict], sahifa: int, callback_prefiks: str, sahifalash_prefiksi: str
) -> InlineKeyboardMarkup:
    boshlanish = sahifa * SAHIFA_HAJMI
    tugash = boshlanish + SAHIFA_HAJMI
    joriy_sahifa = royxat[boshlanish:tugash]

    kb = InlineKeyboardBuilder()
    for i, _ in enumerate(joriy_sahifa, start=1):
        indeks = boshlanish + i - 1
        kb.add(InlineKeyboardButton(text=str(i), callback_data=f"{callback_prefiks}:{indeks}"))
    kb.adjust(5)

    navigatsiya = []
    if sahifa > 0:
        navigatsiya.append(
            InlineKeyboardButton(text="⬅️ Oldingi sahifa", callback_data=f"{sahifalash_prefiksi}:{sahifa - 1}")
        )
    if tugash < len(royxat):
        navigatsiya.append(
            InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"{sahifalash_prefiksi}:{sahifa + 1}")
        )
    if navigatsiya:
        kb.row(*navigatsiya)

    kb.row(ORQAGA_TUGMASI, BEKOR_TUGMASI)
    return kb.as_markup()


def sana_klaviaturasi() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 Bugun", callback_data="sana:bugun")
    kb.adjust(1)
    kb.row(ORQAGA_TUGMASI, BEKOR_TUGMASI)
    return kb.as_markup()


def tolov_klaviaturasi() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⏭️ To'lov yo'q, keyinroq kiritiladi", callback_data="tolov:yoq")
    kb.adjust(1)
    kb.row(ORQAGA_TUGMASI, BEKOR_TUGMASI)
    return kb.as_markup()


def yana_guruh_klaviaturasi() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Ha, yana guruhga yozish", callback_data="yana_guruh:ha")
    kb.button(text="✅ Yo'q, davom et", callback_data="yana_guruh:yoq")
    kb.adjust(1)
    kb.row(ORQAGA_TUGMASI, BEKOR_TUGMASI)
    return kb.as_markup()


def xulosa_klaviaturasi() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Ha, saqlash", callback_data="xulosa:tasdiq")
    kb.adjust(1)
    kb.row(ORQAGA_TUGMASI, BEKOR_TUGMASI)
    return kb.as_markup()


def topilmadi_klaviaturasi() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🆕 Yangi talaba sifatida davom etish", callback_data="talaba:yangi_sifatida")
    kb.button(text="🔁 Qaytadan qidirish", callback_data="talaba:qayta_qidirish")
    kb.adjust(1)
    kb.row(ORQAGA_TUGMASI, BEKOR_TUGMASI)
    return kb.as_markup()


def keyingi_talaba_klaviaturasi() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Ha, shu guruhga", callback_data="keyingi:shu_guruh")
    kb.button(text="➕ Ha, boshqa guruhga", callback_data="keyingi:boshqa_guruh")
    kb.button(text="✅ Yo'q, tugatish", callback_data="keyingi:tugatish")
    kb.adjust(1)
    return kb.as_markup()


def duplikat_tgid_klaviaturasi() -> InlineKeyboardMarkup:
    """Telegram ID bo'yicha duplikat topilganda."""
    kb = InlineKeyboardBuilder()
    kb.button(text="🔁 Mavjud talaba sifatida davom etish", callback_data="duplikat:mavjud_tgid")
    kb.adjust(1)
    kb.row(ORQAGA_TUGMASI, BEKOR_TUGMASI)
    return kb.as_markup()


def duplikat_ism_klaviaturasi(royxat: list[dict]) -> InlineKeyboardMarkup:
    """Faqat ism bo'yicha o'xshash talaba(lar) topilganda."""
    kb = InlineKeyboardBuilder()
    for i, _ in enumerate(royxat, start=1):
        kb.add(InlineKeyboardButton(text=str(i), callback_data=f"duplikat_tanlash:{i - 1}"))
    kb.adjust(5)
    kb.row(InlineKeyboardButton(text="✅ Baribir yangi qo'shish", callback_data="duplikat:baribir_yangi"))
    kb.row(ORQAGA_TUGMASI, BEKOR_TUGMASI)
    return kb.as_markup()
