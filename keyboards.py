from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import SAHIFA_HAJMI

BEKOR_TUGMASI = InlineKeyboardButton(text="❌ Bekor qilish", callback_data="bekor")


def asosiy_menyu_klaviaturasi() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Yangi talaba", callback_data="menyu:yangi_talaba")
    return kb.as_markup()


def turi_tanlash_klaviaturasi() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🆕 Yangi talaba", callback_data="turi:yangi")
    kb.button(text="🔁 Mavjud talaba", callback_data="turi:mavjud")
    kb.adjust(1)
    kb.row(BEKOR_TUGMASI)
    return kb.as_markup()


def tgid_klaviaturasi() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⏭️ O'tkazib yuborish", callback_data="tgid:otkazish")
    kb.row(BEKOR_TUGMASI)
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
            InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"{sahifalash_prefiksi}:{sahifa - 1}")
        )
    if tugash < len(royxat):
        navigatsiya.append(
            InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"{sahifalash_prefiksi}:{sahifa + 1}")
        )
    if navigatsiya:
        kb.row(*navigatsiya)

    kb.row(BEKOR_TUGMASI)
    return kb.as_markup()


def sana_klaviaturasi() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 Bugun", callback_data="sana:bugun")
    kb.row(BEKOR_TUGMASI)
    return kb.as_markup()


def tolov_klaviaturasi() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⏭️ To'lov yo'q, keyinroq kiritiladi", callback_data="tolov:yoq")
    kb.row(BEKOR_TUGMASI)
    return kb.as_markup()


def yana_guruh_klaviaturasi() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Ha, yana guruhga yozish", callback_data="yana_guruh:ha")
    kb.button(text="✅ Yo'q, davom et", callback_data="yana_guruh:yoq")
    kb.adjust(1)
    kb.row(BEKOR_TUGMASI)
    return kb.as_markup()


def xulosa_klaviaturasi() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Ha, saqlash", callback_data="xulosa:tasdiq")
    kb.button(text="❌ Bekor qilish", callback_data="bekor")
    kb.adjust(1)
    return kb.as_markup()


def topilmadi_klaviaturasi() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🆕 Yangi talaba sifatida davom etish", callback_data="talaba:yangi_sifatida")
    kb.button(text="🔁 Qaytadan qidirish", callback_data="talaba:qayta_qidirish")
    kb.adjust(1)
    kb.row(BEKOR_TUGMASI)
    return kb.as_markup()


def keyingi_talaba_klaviaturasi() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Ha, shu guruhga", callback_data="keyingi:shu_guruh")
    kb.button(text="➕ Ha, boshqa guruhga", callback_data="keyingi:boshqa_guruh")
    kb.button(text="✅ Yo'q, tugatish", callback_data="keyingi:tugatish")
    kb.adjust(1)
    return kb.as_markup()
