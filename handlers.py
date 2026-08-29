from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import keyboards
import notion_api
from states import TalabaQoshish

router = Router()


# =========================================================
# Boshlanish / asosiy menyu / bekor qilish
# =========================================================

@router.message(Command("start"))
async def start_buyrugi(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Assalomu alaykum! Admin botiga xush kelibsiz.\n\n"
        "Yangi talaba qo'shish uchun pastdagi tugmani bosing.",
        reply_markup=keyboards.asosiy_pastki_klaviatura(),
    )


async def _yangi_talaba_boshlash(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Yangi talabami yoki mavjud talabami?",
        reply_markup=keyboards.turi_tanlash_klaviaturasi(),
    )
    await state.set_state(TalabaQoshish.turi_tanlash)


@router.message(F.text == keyboards.YANGI_TALABA_MATNI)
async def yangi_talaba_tugmasi(message: Message, state: FSMContext) -> None:
    await _yangi_talaba_boshlash(message, state)


@router.message(Command("yangi_talaba"))
async def yangi_talaba_buyrugi(message: Message, state: FSMContext) -> None:
    await _yangi_talaba_boshlash(message, state)


@router.callback_query(F.data == "bekor")
async def bekor_qilish(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await callback.message.answer(
        "❌ Bekor qilindi. Hech narsa saqlanmadi.\n"
        "Qaytadan boshlash uchun pastdagi tugmani bosing."
    )


# =========================================================
# Talaba turi: Yangi yoki Mavjud
# =========================================================

@router.callback_query(TalabaQoshish.turi_tanlash, F.data == "turi:yangi")
async def turi_yangi(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(is_new=True, yozilishlar=[], guruh_belgilangan=False)
    await callback.message.answer("👤 Talaba ismini kiriting:")
    await state.set_state(TalabaQoshish.ism_kiritish)


@router.callback_query(TalabaQoshish.turi_tanlash, F.data == "turi:mavjud")
async def turi_mavjud(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(is_new=False, yozilishlar=[], guruh_belgilangan=False)
    await callback.message.answer("🔎 Qidirish uchun talaba ismini kiriting:")
    await state.set_state(TalabaQoshish.mavjud_qidirish)


# =========================================================
# Yangi talaba: Ism va Telegram ID
# =========================================================

@router.message(TalabaQoshish.ism_kiritish)
async def ism_qabul(message: Message, state: FSMContext) -> None:
    ism = (message.text or "").strip()
    if len(ism) < 2:
        await message.answer("❌ Ism juda qisqa. Qaytadan kiriting:")
        return
    await state.update_data(ism=ism, talaba_id=None)
    await message.answer(
        "🆔 Telegram ID (ixtiyoriy):\n"
        "Talabaning istalgan xabarini forward qiling, yoki ID raqamini yozing.",
        reply_markup=keyboards.tgid_klaviaturasi(),
    )
    await state.set_state(TalabaQoshish.telegram_id_kutish)


async def _telegram_id_dan_keyin(target, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("guruh_belgilangan"):
        await target.answer(
            "📅 Boshlagan sanani kiriting:\n"
            "Bugun bo'lsa tugmani bosing, aks holda KK.OO.YYYY formatda yozing "
            "(masalan 25.08.2026).",
            reply_markup=keyboards.sana_klaviaturasi(),
        )
        await state.set_state(TalabaQoshish.sana_kutish)
    else:
        await _ustoz_royxatini_korsat(target, state)


@router.callback_query(TalabaQoshish.telegram_id_kutish, F.data == "tgid:otkazish")
async def tgid_otkazish(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(telegram_id=None)
    await _telegram_id_dan_keyin(callback.message, state)


@router.message(TalabaQoshish.telegram_id_kutish)
async def telegram_id_qabul(message: Message, state: FSMContext) -> None:
    telegram_id = None
    if message.forward_origin:
        sender = getattr(message.forward_origin, "sender_user", None)
        if sender:
            telegram_id = str(sender.id)
        else:
            await message.answer(
                "⚠️ Bu foydalanuvchi ID'ni yashirgan (maxfiylik sozlamasi). "
                "Qo'lda kiriting yoki 'O'tkazib yuborish' tugmasini bosing."
            )
            return
    elif message.text and message.text.strip().isdigit():
        telegram_id = message.text.strip()
    else:
        await message.answer(
            "❌ Telegram ID topilmadi. Talabaning xabarini forward qiling, "
            "ID raqamini yozing, yoki 'O'tkazib yuborish' tugmasini bosing."
        )
        return

    await message.answer(f"✅ Telegram ID olindi: {telegram_id}")
    await state.update_data(telegram_id=telegram_id)
    await _telegram_id_dan_keyin(message, state)


# =========================================================
# Mavjud talaba: qidirish va tanlash
# =========================================================

@router.message(TalabaQoshish.mavjud_qidirish)
async def mavjud_qidiruv(message: Message, state: FSMContext) -> None:
    ism_qismi = (message.text or "").strip()
    if len(ism_qismi) < 2:
        await message.answer("❌ Kamida 2 ta harf kiriting:")
        return

    try:
        natijalar = await notion_api.talaba_qidirish(ism_qismi)
    except Exception as xato:
        await message.answer(
            f"❌ Qidiruvda xatolik: {xato}\n"
            "Notion integratsiyasi Talabalar bazasiga ulanganini tekshiring."
        )
        return
    await state.update_data(ism=ism_qismi)

    if not natijalar:
        await message.answer(
            f"❌ \"{ism_qismi}\" bo'yicha talaba topilmadi.",
            reply_markup=keyboards.topilmadi_klaviaturasi(),
        )
        await state.set_state(TalabaQoshish.mavjud_tanlash)
        return

    await state.update_data(mavjud_list=natijalar)
    matn = keyboards.raqamli_royxat_matni("🔎 Topilgan talabalar:", natijalar, "ism", 0)
    kb = keyboards.raqamli_royxat_klaviaturasi(natijalar, 0, "talaba", "page:mavjud")
    await message.answer(matn, reply_markup=kb)
    await state.set_state(TalabaQoshish.mavjud_tanlash)


@router.callback_query(TalabaQoshish.mavjud_tanlash, F.data.startswith("page:mavjud:"))
async def mavjud_sahifalash(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    sahifa = int(callback.data.split(":")[2])
    data = await state.get_data()
    natijalar = data["mavjud_list"]
    matn = keyboards.raqamli_royxat_matni("🔎 Topilgan talabalar:", natijalar, "ism", sahifa)
    kb = keyboards.raqamli_royxat_klaviaturasi(natijalar, sahifa, "talaba", "page:mavjud")
    await callback.message.answer(matn, reply_markup=kb)


@router.callback_query(TalabaQoshish.mavjud_tanlash, F.data.startswith("talaba:"))
async def mavjud_talaba_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    qism = callback.data.split(":", 1)[1]

    if qism == "yangi_sifatida":
        await state.update_data(is_new=True, talaba_id=None, telegram_id=None)
        await callback.message.answer(
            "🆔 Telegram ID (ixtiyoriy):\n"
            "Talabaning istalgan xabarini forward qiling, yoki ID raqamini yozing.",
            reply_markup=keyboards.tgid_klaviaturasi(),
        )
        await state.set_state(TalabaQoshish.telegram_id_kutish)
        return

    if qism == "qayta_qidirish":
        await callback.message.answer("🔎 Qidirish uchun ismni kiriting:")
        await state.set_state(TalabaQoshish.mavjud_qidirish)
        return

    idx = int(qism)
    data = await state.get_data()
    talaba = data["mavjud_list"][idx]
    await state.update_data(talaba_id=talaba["id"], ism=talaba["ism"], telegram_id=None)
    await _ustoz_royxatini_korsat(callback.message, state)


# =========================================================
# Ustoz tanlash
# =========================================================

async def _ustoz_royxatini_korsat(target, state: FSMContext, sahifa: int = 0) -> None:
    data = await state.get_data()
    ustozlar = data.get("ustozlar_list")
    if ustozlar is None:
        try:
            ustozlar = await notion_api.faol_ustozlar()
        except Exception as xato:
            await target.answer(
                f"❌ Ustozlar ro'yxatini olishda xatolik: {xato}\n"
                "Notion integratsiyasi Ustozlar bazasiga ulanganini tekshiring."
            )
            return
        await state.update_data(ustozlar_list=ustozlar)

    if not ustozlar:
        await target.answer("⚠️ Faol ustozlar topilmadi. Notion'da Ustozlar holatini tekshiring.")
        return

    matn = keyboards.raqamli_royxat_matni("👨‍🏫 Ustozni tanlang:", ustozlar, "ism", sahifa)
    kb = keyboards.raqamli_royxat_klaviaturasi(ustozlar, sahifa, "ustoz", "page:ustoz")
    await target.answer(matn, reply_markup=kb)
    await state.set_state(TalabaQoshish.ustoz_tanlash)


@router.callback_query(TalabaQoshish.ustoz_tanlash, F.data.startswith("page:ustoz:"))
async def ustoz_sahifalash(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    sahifa = int(callback.data.split(":")[2])
    await _ustoz_royxatini_korsat(callback.message, state, sahifa)


@router.callback_query(TalabaQoshish.ustoz_tanlash, F.data.startswith("ustoz:"))
async def ustoz_tanlandi(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    idx = int(callback.data.split(":")[1])
    data = await state.get_data()
    ustoz = data["ustozlar_list"][idx]
    await state.update_data(
        cur_ustoz_id=ustoz["id"], cur_ustoz_ism=ustoz["ism"], guruhlar_list=None
    )
    await _guruh_royxatini_korsat(callback.message, state)


# =========================================================
# Guruh tanlash
# =========================================================

async def _guruh_royxatini_korsat(target, state: FSMContext, sahifa: int = 0) -> None:
    data = await state.get_data()
    guruhlar = data.get("guruhlar_list")
    if guruhlar is None:
        try:
            guruhlar = await notion_api.ustoz_faol_guruhlari(data["cur_ustoz_id"])
        except Exception as xato:
            await target.answer(
                f"❌ Guruhlar ro'yxatini olishda xatolik: {xato}\n"
                "Notion integratsiyasi Guruhlar bazasiga ulanganini tekshiring."
            )
            return
        await state.update_data(guruhlar_list=guruhlar)

    if not guruhlar:
        await target.answer(
            f"⚠️ {data['cur_ustoz_ism']} ustozining Faol guruhi topilmadi. Boshqa ustoz tanlang."
        )
        await _ustoz_royxatini_korsat(target, state)
        return

    matn = keyboards.raqamli_royxat_matni(
        f"📚 {data['cur_ustoz_ism']} — guruhni tanlang:", guruhlar, "nomi", sahifa
    )
    kb = keyboards.raqamli_royxat_klaviaturasi(guruhlar, sahifa, "guruh", "page:guruh")
    await target.answer(matn, reply_markup=kb)
    await state.set_state(TalabaQoshish.guruh_tanlash)


@router.callback_query(TalabaQoshish.guruh_tanlash, F.data.startswith("page:guruh:"))
async def guruh_sahifalash(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    sahifa = int(callback.data.split(":")[2])
    await _guruh_royxatini_korsat(callback.message, state, sahifa)


@router.callback_query(TalabaQoshish.guruh_tanlash, F.data.startswith("guruh:"))
async def guruh_tanlandi(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    idx = int(callback.data.split(":")[1])
    data = await state.get_data()
    guruh = data["guruhlar_list"][idx]
    await state.update_data(cur_guruh_id=guruh["id"], cur_guruh_nomi=guruh["nomi"])
    await callback.message.answer(
        "📅 Boshlagan sanani kiriting:\n"
        "Bugun bo'lsa tugmani bosing, aks holda KK.OO.YYYY formatda yozing "
        "(masalan 25.08.2026).",
        reply_markup=keyboards.sana_klaviaturasi(),
    )
    await state.set_state(TalabaQoshish.sana_kutish)


# =========================================================
# Boshlagan sana
# =========================================================

async def _sanadan_keyin(target, state: FSMContext, iso_sana: str) -> None:
    await state.update_data(cur_sana=iso_sana)
    data = await state.get_data()
    if data["is_new"]:
        await target.answer(
            "💵 Dastlabki to'lovni kiriting (so'm):",
            reply_markup=keyboards.tolov_klaviaturasi(),
        )
        await state.set_state(TalabaQoshish.tolov_kutish)
    else:
        await _yozilish_qoshish(state, tolov=None)
        await _yana_guruh_sora(target, state)


@router.callback_query(TalabaQoshish.sana_kutish, F.data == "sana:bugun")
async def sana_bugun(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await _sanadan_keyin(callback.message, state, notion_api.bugun())


@router.message(TalabaQoshish.sana_kutish)
async def sana_qolda(message: Message, state: FSMContext) -> None:
    iso_sana = notion_api.sana_kk_oo_yyyy_dan(message.text or "")
    if not iso_sana:
        await message.answer("❌ Sana formati noto'g'ri. Masalan: 25.08.2026")
        return
    await _sanadan_keyin(message, state, iso_sana)


# =========================================================
# Dastlabki to'lov (faqat yangi talaba)
# =========================================================

async def _yozilish_qoshish(state: FSMContext, tolov) -> None:
    data = await state.get_data()
    yozilishlar = data.get("yozilishlar", [])
    yozilishlar.append(
        {
            "guruh_id": data["cur_guruh_id"],
            "guruh_nomi": data["cur_guruh_nomi"],
            "sana": data["cur_sana"],
            "tolov": tolov,
        }
    )
    await state.update_data(yozilishlar=yozilishlar)


async def _yana_guruh_sora(target, state: FSMContext) -> None:
    await target.answer(
        "➕ Yana guruhga ham yozamizmi?", reply_markup=keyboards.yana_guruh_klaviaturasi()
    )
    await state.set_state(TalabaQoshish.yana_guruh)


@router.callback_query(TalabaQoshish.tolov_kutish, F.data == "tolov:yoq")
async def tolov_yoq(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await _yozilish_qoshish(state, tolov=None)
    await _yana_guruh_sora(callback.message, state)


@router.message(TalabaQoshish.tolov_kutish)
async def tolov_qolda(message: Message, state: FSMContext) -> None:
    matn = (message.text or "").replace(" ", "").replace(",", "")
    try:
        summa = float(matn)
        if summa <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Summani musbat raqam bilan kiriting, masalan: 500000")
        return
    await _yozilish_qoshish(state, tolov=summa)
    await _yana_guruh_sora(message, state)


# =========================================================
# Yana guruhga yozish tsikli
# =========================================================

@router.callback_query(TalabaQoshish.yana_guruh, F.data == "yana_guruh:ha")
async def yana_guruh_ha(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(
        cur_ustoz_id=None,
        cur_ustoz_ism=None,
        cur_guruh_id=None,
        cur_guruh_nomi=None,
        cur_sana=None,
        guruhlar_list=None,
    )
    await _ustoz_royxatini_korsat(callback.message, state)


@router.callback_query(TalabaQoshish.yana_guruh, F.data == "yana_guruh:yoq")
async def yana_guruh_yoq(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await _xulosa_korsat(callback.message, state)


# =========================================================
# Xulosa va tasdiqlash
# =========================================================

def _tolov_matni(tolov) -> str:
    if not tolov:
        return "yo'q"
    return f"{int(tolov):,} so'm".replace(",", " ")


async def _xulosa_korsat(target, state: FSMContext) -> None:
    data = await state.get_data()
    qatorlar = ["📋 Yangi talaba:" if data["is_new"] else "📋 Mavjud talaba:", f"Ism: {data['ism']}"]
    if data.get("telegram_id"):
        qatorlar.append(f"Telegram ID: {data['telegram_id']}")
    qatorlar.append("")

    yozilishlar = data.get("yozilishlar", [])
    if len(yozilishlar) == 1:
        y = yozilishlar[0]
        qatorlar.append(f"Guruh: {y['guruh_nomi']}")
        qatorlar.append(f"Boshlagan sana: {notion_api.sana_ozbekcha(y['sana'])}")
        if data["is_new"]:
            qatorlar.append(f"Dastlabki to'lov: {_tolov_matni(y['tolov'])}")
    else:
        for i, y in enumerate(yozilishlar, start=1):
            qator = f"{i}) {y['guruh_nomi']} | {notion_api.sana_ozbekcha(y['sana'])}"
            if data["is_new"]:
                qator += f" | To'lov: {_tolov_matni(y['tolov'])}"
            qatorlar.append(qator)

    qatorlar.append("")
    qatorlar.append("✅ Tasdiqlaysizmi?")
    await target.answer("\n".join(qatorlar), reply_markup=keyboards.xulosa_klaviaturasi())
    await state.set_state(TalabaQoshish.xulosa_tasdiq)


@router.callback_query(TalabaQoshish.xulosa_tasdiq, F.data == "xulosa:tasdiq")
async def xulosa_tasdiqlandi(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    message = callback.message

    talaba_id = data.get("talaba_id")
    if not talaba_id:
        try:
            talaba_id = await notion_api.talaba_yaratish(data["ism"], data.get("telegram_id"))
            await state.update_data(talaba_id=talaba_id)
            await message.answer("✅ Talaba yaratildi")
        except Exception as xato:
            await message.answer(
                f"❌ Talaba yaratilmadi: {xato}\nHech narsa saqlanmadi. Qaytadan urinib ko'ring."
            )
            return

    songi_guruh_id = None
    songi_guruh_nomi = None

    for y in data.get("yozilishlar", []):
        try:
            await notion_api.yozilish_yaratish(
                talaba_id, data["ism"], y["guruh_id"], y["guruh_nomi"], y["sana"]
            )
            await message.answer(f"✅ {y['guruh_nomi']} guruhiga yozildi")
            songi_guruh_id = y["guruh_id"]
            songi_guruh_nomi = y["guruh_nomi"]
        except Exception as xato:
            await message.answer(
                f"⚠️ {y['guruh_nomi']} uchun Yozilish yaratilmadi: {xato}\n"
                "Qo'lda qo'shing. Davom etyapman."
            )
            continue

        if y.get("tolov"):
            try:
                await notion_api.tolov_yaratish(talaba_id, data["ism"], y["tolov"])
                await message.answer("✅ To'lov qo'shildi")
            except Exception as xato:
                await message.answer(
                    f"⚠️ To'lov qo'shilmadi ({y['guruh_nomi']}): {xato}\n"
                    "Yozilish saqlangan, to'lovni qo'lda kiriting."
                )

    await message.answer("🎉 Jarayon yakunlandi.")

    await state.update_data(shu_guruh_id=songi_guruh_id, shu_guruh_nomi=songi_guruh_nomi)
    await message.answer(
        "Yana talaba qo'shamizmi?", reply_markup=keyboards.keyingi_talaba_klaviaturasi()
    )
    await state.set_state(TalabaQoshish.keyingi_talaba)


# =========================================================
# Saqlangandan keyin: yana talaba qo'shish
# =========================================================

@router.callback_query(TalabaQoshish.keyingi_talaba, F.data == "keyingi:tugatish")
async def keyingi_tugatish(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await callback.message.answer(
        "Rahmat! Ishingiz muvaffaqiyatli yakunlandi. ✅\n"
        "Yana talaba qo'shish uchun pastdagi tugmani bosing."
    )
    await state.clear()


@router.callback_query(TalabaQoshish.keyingi_talaba, F.data == "keyingi:boshqa_guruh")
async def keyingi_boshqa_guruh(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    await state.set_data({"ustozlar_list": data.get("ustozlar_list")})
    await state.update_data(is_new=True, yozilishlar=[], guruh_belgilangan=False)
    await callback.message.answer("👤 Talaba ismini kiriting:")
    await state.set_state(TalabaQoshish.ism_kiritish)


@router.callback_query(TalabaQoshish.keyingi_talaba, F.data == "keyingi:shu_guruh")
async def keyingi_shu_guruh(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    shu_guruh_id = data.get("shu_guruh_id")
    shu_guruh_nomi = data.get("shu_guruh_nomi")

    if not shu_guruh_id:
        await keyingi_boshqa_guruh(callback, state)
        return

    await state.set_data({"ustozlar_list": data.get("ustozlar_list")})
    await state.update_data(
        is_new=True,
        yozilishlar=[],
        cur_guruh_id=shu_guruh_id,
        cur_guruh_nomi=shu_guruh_nomi,
        guruh_belgilangan=True,
        shu_guruh_id=shu_guruh_id,
        shu_guruh_nomi=shu_guruh_nomi,
    )
    await callback.message.answer(f"👤 Talaba ismini kiriting ({shu_guruh_nomi} guruhiga yoziladi):")
    await state.set_state(TalabaQoshish.ism_kiritish)
