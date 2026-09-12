from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import keyboards
import notion_api
from config import KURSLAR

router = Router()


def _summa_matni(summa) -> str:
    if not summa:
        return "kiritilmagan"
    return f"{int(summa):,} so'm".replace(",", " ")


def _guruh_blokini_tuz(i: int, guruh: dict, ustoz_lugati: dict, yozilishlar_soni: dict, ustozni_korsat: bool) -> str:
    qatorlar = [f"{i}) {guruh['nomi']}"]
    qatorlar.append(
        f"🗓 Kunlar: {', '.join(guruh['dars_kunlari'])}" if guruh["dars_kunlari"] else "🗓 Kunlar: kiritilmagan"
    )
    qatorlar.append(f"🕐 Vaqt: {guruh['dars_vaqti'] or 'kiritilmagan'}")
    if ustozni_korsat:
        if guruh["ustoz_id"]:
            ustoz_ism = ustoz_lugati.get(guruh["ustoz_id"], "noma'lum")
        else:
            ustoz_ism = "biriktirilmagan"
        qatorlar.append(f"👨‍🏫 Ustoz: {ustoz_ism}")
    soni = yozilishlar_soni.get(guruh["id"], 0)
    qatorlar.append(f"👥 O'quvchilar: {soni}")
    qatorlar.append(f"💰 Narx: {_summa_matni(guruh['oylik_tolov'])}")
    return "\n".join(qatorlar)


async def _guruhlarni_yubor(message: Message, sarlavha: str, guruhlar: list[dict], ustozni_korsat: bool) -> None:
    if not guruhlar:
        await message.answer(
            f"{sarlavha}\n\nFaol guruh topilmadi.", reply_markup=keyboards.hisobot_yakun_klaviaturasi()
        )
        return

    try:
        ustoz_lugati = await notion_api.barcha_ustozlar_lugati() if ustozni_korsat else {}
    except Exception:
        ustoz_lugati = {}
    try:
        yozilishlar_soni = await notion_api.faol_yozilishlar_soni_guruh_boyicha()
    except Exception:
        yozilishlar_soni = {}

    bloklar = [
        _guruh_blokini_tuz(i, g, ustoz_lugati, yozilishlar_soni, ustozni_korsat)
        for i, g in enumerate(guruhlar, start=1)
    ]

    xabar = f"{sarlavha} ({len(guruhlar)} ta):\n\n"
    for blok in bloklar:
        if len(xabar) + len(blok) + 2 > 3500:
            await message.answer(xabar.rstrip())
            xabar = ""
        xabar += blok + "\n\n"
    if xabar.strip():
        await message.answer(xabar.rstrip(), reply_markup=keyboards.hisobot_yakun_klaviaturasi())


@router.message(F.text == keyboards.GURUHLAR_MATNI)
async def guruhlar_tugmasi(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "📊 Guruhlarni qanday ko'rmoqchisiz?", reply_markup=keyboards.hisobot_fork_klaviaturasi()
    )


@router.callback_query(F.data == "hisobot_fork")
async def hisobot_fork(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await callback.message.answer(
        "📊 Guruhlarni qanday ko'rmoqchisiz?", reply_markup=keyboards.hisobot_fork_klaviaturasi()
    )


@router.callback_query(F.data == "hisobot:kurs")
async def hisobot_kurs_menyu(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await callback.message.answer(
        keyboards.kurslar_matni(KURSLAR), reply_markup=keyboards.kurslar_klaviaturasi(KURSLAR)
    )


@router.callback_query(F.data.startswith("hkurs:"))
async def hisobot_kurs_tanlandi(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    idx = int(callback.data.split(":")[1])
    kurs = KURSLAR[idx]
    try:
        guruhlar = await notion_api.kurs_boyicha_faol_guruhlar(kurs)
    except Exception as xato:
        await callback.message.answer(f"❌ Xatolik: {xato}")
        return
    await _guruhlarni_yubor(callback.message, f"📚 {kurs} — Faol guruhlar", guruhlar, ustozni_korsat=True)


@router.callback_query(F.data == "hisobot:ustoz")
async def hisobot_ustoz_menyu(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    try:
        ustozlar = await notion_api.faol_ustozlar()
    except Exception as xato:
        await callback.message.answer(f"❌ Xatolik: {xato}")
        return
    if not ustozlar:
        await callback.message.answer("⚠️ Faol ustozlar topilmadi.")
        return
    await state.update_data(hisobot_ustozlar_list=ustozlar)
    matn = keyboards.raqamli_royxat_matni("👨‍🏫 Ustozni tanlang:", ustozlar, "ism", 0)
    kb = keyboards.hisobot_royxat_klaviaturasi(ustozlar, 0, "hustoz", "hustoz_sahifa")
    await callback.message.answer(matn, reply_markup=kb)


@router.callback_query(F.data.startswith("hustoz_sahifa:"))
async def hisobot_ustoz_sahifalash(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    sahifa = int(callback.data.split(":")[1])
    data = await state.get_data()
    ustozlar = data.get("hisobot_ustozlar_list", [])
    matn = keyboards.raqamli_royxat_matni("👨‍🏫 Ustozni tanlang:", ustozlar, "ism", sahifa)
    kb = keyboards.hisobot_royxat_klaviaturasi(ustozlar, sahifa, "hustoz", "hustoz_sahifa")
    await callback.message.answer(matn, reply_markup=kb)


@router.callback_query(F.data.startswith("hustoz:"))
async def hisobot_ustoz_tanlandi(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    idx = int(callback.data.split(":")[1])
    data = await state.get_data()
    ustoz = data["hisobot_ustozlar_list"][idx]
    try:
        guruhlar = await notion_api.ustoz_faol_guruhlari_toliq(ustoz["id"])
    except Exception as xato:
        await callback.message.answer(f"❌ Xatolik: {xato}")
        return
    guruhlar.sort(key=lambda g: g["nomi"])
    await _guruhlarni_yubor(
        callback.message, f"👨‍🏫 {ustoz['ism']} — Faol guruhlari", guruhlar, ustozni_korsat=False
    )
