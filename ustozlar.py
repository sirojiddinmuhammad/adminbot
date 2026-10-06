from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import keyboards
import notion_api
from states import OylikBerish

router = Router()


def _summa_matni(summa) -> str:
    if not summa:
        return "0 so'm"
    ishora = "-" if summa < 0 else ""
    return f"{ishora}{int(abs(summa)):,} so'm".replace(",", " ")


@router.message(F.text == keyboards.USTOZLAR_MATNI)
async def ustozlar_tugmasi(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _ustozlar_royxatini_korsat(message, state)


@router.callback_query(F.data == "ustozlar_royxati")
async def ustozlar_royxati_qayta(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await _ustozlar_royxatini_korsat(callback.message, state)


async def _ustozlar_royxatini_korsat(message: Message, state: FSMContext) -> None:
    try:
        ustozlar = await notion_api.faol_ustozlar()
    except Exception as xato:
        await message.answer(f"❌ Xatolik: {xato}")
        return
    if not ustozlar:
        await message.answer("⚠️ Faol ustozlar topilmadi.")
        return

    await state.update_data(panel_ustozlar_list=ustozlar)
    matn = keyboards.raqamli_royxat_matni("👨‍🏫 Ustozni tanlang:", ustozlar, "ism", 0)
    kb = keyboards.ustoz_panel_royxat_klaviaturasi(ustozlar, 0)
    await message.answer(matn, reply_markup=kb)


@router.callback_query(F.data.startswith("ustoz_panel_sahifa:"))
async def ustoz_panel_sahifalash(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    sahifa = int(callback.data.split(":")[1])
    data = await state.get_data()
    ustozlar = data.get("panel_ustozlar_list", [])
    matn = keyboards.raqamli_royxat_matni("👨‍🏫 Ustozni tanlang:", ustozlar, "ism", sahifa)
    kb = keyboards.ustoz_panel_royxat_klaviaturasi(ustozlar, sahifa)
    await callback.message.answer(matn, reply_markup=kb)


@router.callback_query(F.data.startswith("ustoz_panel:"))
async def ustoz_panelini_korsat(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    idx = int(callback.data.split(":")[1])
    data = await state.get_data()
    ustoz = data["panel_ustozlar_list"][idx]

    try:
        moliya = await notion_api.ustoz_moliyaviy_malumot(ustoz["id"])
    except Exception as xato:
        await callback.message.answer(f"❌ Moliyaviy ma'lumotni olishda xatolik: {xato}")
        return

    try:
        guruhlar = await notion_api.ustoz_faol_guruhlari_toliq(ustoz["id"])
    except Exception as xato:
        await callback.message.answer(f"❌ Guruhlarni olishda xatolik: {xato}")
        return

    guruh_idlari = [g["id"] for g in guruhlar]

    try:
        yozilishlar_soni = await notion_api.faol_yozilishlar_soni_guruh_boyicha()
    except Exception:
        yozilishlar_soni = {}
    talabalar_soni = sum(yozilishlar_soni.get(gid, 0) for gid in guruh_idlari)

    try:
        otilgan_soni = await notion_api.darslar_soni(guruh_idlari, "Dars o'tildi")
    except Exception:
        otilgan_soni = 0

    try:
        belgilanmaganlar = await notion_api.belgilanmagan_otgan_darslar(guruh_idlari)
    except Exception:
        belgilanmaganlar = []

    guruh_nomlari = {g["id"]: g["nomi"] for g in guruhlar}

    qatorlar = [
        f"👨‍🏫 {ustoz['ism']}",
        "",
        f"💰 Balans: {_summa_matni(moliya['balans'])}",
        f"📈 Ishlab topgani: {_summa_matni(moliya['ishlab_topgani'])}",
        f"💸 Berilgan oyliklar: {_summa_matni(moliya['berilgan_oyliklar'])}",
        "",
        f"📚 Guruhlari: {len(guruhlar)} ta (Faol)",
        f"🎓 Talabalari: {talabalar_soni} ta",
        f"✅ O'tilgan darslar: {otilgan_soni} ta",
        "",
    ]

    if belgilanmaganlar:
        qatorlar.append(f"⏳ Belgilanmagan darslar (muddati o'tgan): {len(belgilanmaganlar)} ta")
        for d in belgilanmaganlar[:10]:
            guruh_nomi = guruh_nomlari.get(d["guruh_id"], "noma'lum guruh")
            sana_matni = notion_api.sana_ozbekcha(d["sana"]) if d["sana"] else "sanasiz"
            qatorlar.append(f"  • {guruh_nomi} — {sana_matni}")
        if len(belgilanmaganlar) > 10:
            qatorlar.append(f"  ... va yana {len(belgilanmaganlar) - 10} ta")
    else:
        qatorlar.append("⏳ Belgilanmagan (muddati o'tgan) darslar yo'q ✅")

    await state.update_data(panel_tanlangan_ustoz=ustoz)
    await callback.message.answer(
        "\n".join(qatorlar), reply_markup=keyboards.ustoz_paneli_klaviaturasi(idx)
    )


# =========================================================
# Oylik berish
# =========================================================

@router.callback_query(F.data.startswith("oylik_berish:"))
async def oylik_berish_boshlash(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    idx = int(callback.data.split(":")[1])
    data = await state.get_data()
    ustoz = data["panel_ustozlar_list"][idx]
    await state.update_data(oylik_ustoz_id=ustoz["id"], oylik_ustoz_ism=ustoz["ism"])
    await callback.message.answer(
        f"💵 {ustoz['ism']} uchun oylik summasini kiriting (so'm):",
        reply_markup=keyboards.oylik_bekor_klaviaturasi(),
    )
    await state.set_state(OylikBerish.summa_kutish)


@router.callback_query(F.data == "oylik_bekor")
async def oylik_bekor(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    await state.set_data({"panel_ustozlar_list": data.get("panel_ustozlar_list")})
    await callback.message.answer("❌ Oylik berish bekor qilindi.")


@router.message(OylikBerish.summa_kutish)
async def oylik_summa_qabul(message: Message, state: FSMContext) -> None:
    matn = (message.text or "").replace(" ", "").replace(",", "")
    try:
        summa = float(matn)
        if summa <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Summani musbat raqam bilan kiriting, masalan: 300000")
        return

    await state.update_data(oylik_summa=summa)
    await message.answer(
        "📅 Sanani tanlang yoki KK.OO.YYYY formatda yozing (masalan 25.08.2026):",
        reply_markup=keyboards.oylik_sana_klaviaturasi(),
    )
    await state.set_state(OylikBerish.sana_kutish)


async def _oylikni_saqla(target, state: FSMContext, iso_sana: str) -> None:
    data = await state.get_data()
    try:
        await notion_api.oylik_yaratish(data["oylik_ustoz_id"], data["oylik_summa"], iso_sana)
    except Exception as xato:
        await target.answer(f"❌ Oylik yozilmadi: {xato}")
        return

    summa_matni = f"{int(data['oylik_summa']):,} so'm".replace(",", " ")
    await target.answer(
        f"✅ Oylik yozildi: {data['oylik_ustoz_ism']} — {summa_matni} — "
        f"{notion_api.sana_ozbekcha(iso_sana)}"
    )
    await state.set_data({"panel_ustozlar_list": data.get("panel_ustozlar_list")})


@router.callback_query(OylikBerish.sana_kutish, F.data == "oylik_sana:bugun")
async def oylik_sana_bugun(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await _oylikni_saqla(callback.message, state, notion_api.bugun())


@router.callback_query(OylikBerish.sana_kutish, F.data == "oylik_sana:kecha")
async def oylik_sana_kecha(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await _oylikni_saqla(callback.message, state, notion_api.kecha())


@router.message(OylikBerish.sana_kutish)
async def oylik_sana_qolda(message: Message, state: FSMContext) -> None:
    iso_sana = notion_api.sana_kk_oo_yyyy_dan(message.text or "")
    if not iso_sana:
        await message.answer("❌ Sana formati noto'g'ri. Masalan: 25.08.2026")
        return
    await _oylikni_saqla(message, state, iso_sana)
