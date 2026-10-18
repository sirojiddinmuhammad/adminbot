import html
import re

from aiogram import F, Router
from aiogram.types import CallbackQuery

import notion_api
from config import ADMIN_ID

router = Router()

# Ikki marta bosilishdan himoya: hozir ishlanayotgan yozilish ID'lari
_jarayonda: set[str] = set()

_HEX32 = re.compile(r"^[0-9a-fA-F]{32}$")
_UUID = re.compile(r"^[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$")


def _talaba_ismi(callback: CallbackQuery) -> str:
    """Ustozlar boti yuborgan xabar matnidan 'Talaba: ...' qatorini oladi."""
    # .text oddiy matn (entity'larsiz) qaytaradi; qatorni satr boshidan qidiramiz
    matn = callback.message.text or callback.message.caption or ""
    mos = re.search(r"^Talaba:[ \t]*(\S.*)$", matn, flags=re.MULTILINE)
    return mos.group(1).strip() if mos else "Talaba"


def _id_tekshir(page_id: str) -> bool:
    return bool(_HEX32.match(page_id) or _UUID.match(page_id))


async def _bajar(callback: CallbackQuery, amal: str) -> None:
    # Faqat admin
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return

    page_id = callback.data.split(":", 1)[1]
    if not _id_tekshir(page_id):
        await callback.answer("❌ Noto'g'ri ID", show_alert=True)
        return

    if page_id in _jarayonda:
        await callback.answer("⏳ Jarayonda...")
        return
    _jarayonda.add(page_id)

    ism = _talaba_ismi(callback)
    try:
        if amal == "davom":
            await notion_api.yozilishni_davom_ettirish(page_id)
            yangi_matn = f"✅ Davom etadi — {html.escape(ism)} o'qishga qaytarildi."
        else:
            await notion_api.yozilishni_tugatish(page_id, "3 dars ketma-ket kelmadi")
            yangi_matn = f"🚪 Guruhdan chiqarildi — {html.escape(ism)}."
    except notion_api.NotionXato as xato:
        _jarayonda.discard(page_id)
        qosimcha = ""
        if xato.status == 404:
            qosimcha = "\nIntegratsiya Yozilishlar bazasiga ulanmagan bo'lishi mumkin."
        await callback.answer("❌ Notion xatosi", show_alert=False)
        await callback.message.answer(
            f"❌ Notion xatosi ({html.escape(ism)}): {html.escape(str(xato))}{qosimcha}\n"
            "Xabar o'zgartirilmadi, tugmalarni qayta bosishingiz mumkin."
        )
        return
    except Exception as xato:
        _jarayonda.discard(page_id)
        await callback.answer("❌ Xatolik", show_alert=False)
        await callback.message.answer(
            f"❌ Kutilmagan xatolik ({html.escape(ism)}): {html.escape(str(xato))}\n"
            "Xabar o'zgartirilmadi."
        )
        return

    # Muvaffaqiyatli: matnni almashtiramiz, tugmalar yo'qoladi
    try:
        await callback.message.edit_text(yangi_matn, reply_markup=None)
    except Exception:
        # Matn tahrirlanmasa ham tugmalarni olib tashlaymiz
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    await callback.answer("Saqlandi ✅")
    # _jarayonda'dan olib tashlamaymiz: tugmalar yo'qolgan, takroriy bosish kerak emas


@router.callback_query(F.data.startswith("kk_davom:"))
async def kk_davom(callback: CallbackQuery) -> None:
    await _bajar(callback, "davom")


@router.callback_query(F.data.startswith("kk_chiq:"))
async def kk_chiq(callback: CallbackQuery) -> None:
    await _bajar(callback, "chiq")
