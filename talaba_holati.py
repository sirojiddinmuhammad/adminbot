import asyncio
import html

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

import keyboards
import notion_api

router = Router()

MENYU_MATNLARI = [
    keyboards.YANGI_TALABA_MATNI,
    keyboards.GURUHLAR_MATNI,
    keyboards.USTOZLAR_MATNI,
    keyboards.TALABA_HOLATI_MATNI,
]

DAVOMAT_BELGISI = {
    "Darsda qatnashdi": "✅",
    "Darsga kelmadi": "❌",
    "Ta'til": "🏖",
    "Oylik hisob": "🧾",
}

HOLAT_BELGISI = {"O'qiyabdi": "🟢", "Ta'tilda": "🏖", "Tugatdi": "🔴"}

AMALLAR = {
    "tatil": {
        "holatlar": {"O'qiyabdi"},
        "savol": "🏖 {ism} — {guruh}\nTa'tilga chiqarilsinmi?",
        "natija": "🏖 {ism} — {guruh} ta'tilga chiqarildi.",
        "yangi_holat": "Ta'tilda",
    },
    "qayt": {
        "holatlar": {"Ta'tilda"},
        "savol": "▶️ {ism} — {guruh}\nO'qiyabdi holatiga qaytarilsinmi?",
        "natija": "▶️ {ism} — {guruh} o'qishga qaytarildi.",
        "yangi_holat": "O'qiyabdi",
    },
    "chiq": {
        "holatlar": {"O'qiyabdi", "Ta'tilda"},
        "savol": "🚪 {ism} — {guruh}\nGuruhdan chiqarilsinmi?",
        "natija": "🚪 {ism} — {guruh} guruhdan chiqarildi.",
        "yangi_holat": "Tugatdi",
    },
}

# Ikki marta bosilishdan himoya: hozir ishlanayotgan yozilish ID'lari
_jarayonda: set[str] = set()


class TalabaHolati(StatesGroup):
    ism_kutish = State()
    talaba_tanlash = State()
    karta = State()
    guruh_tanlash = State()
    tasdiq = State()


# =========================================================
# Yordamchilar
# =========================================================

def _e(matn) -> str:
    return html.escape(str(matn))


def _pul(summa) -> str:
    ishora = "-" if summa < 0 else ""
    return f"{ishora}{int(abs(summa)):,} so'm".replace(",", " ")


def _sana_qisqa(iso: str | None) -> str:
    if not iso:
        return "?"
    try:
        return notion_api.sana_ozbekcha(iso)[:5]  # KK.OO
    except Exception:
        return iso


def _bekor_klaviaturasi() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Bekor qilish", callback_data="th:bekor")
    return kb.as_markup()


def _karta_klaviaturasi(yozilishlar: list[dict]) -> InlineKeyboardMarkup | None:
    holatlar = {y["holat"] for y in yozilishlar}
    kb = InlineKeyboardBuilder()
    tugmalar_soni = 0
    if "O'qiyabdi" in holatlar:
        kb.button(text="🏖 Ta'tilga chiqarish", callback_data="th:amal:tatil")
        tugmalar_soni += 1
    if "Ta'tilda" in holatlar:
        kb.button(text="▶️ O'qiyabdi ga qaytarish", callback_data="th:amal:qayt")
        tugmalar_soni += 1
    if holatlar & {"O'qiyabdi", "Ta'tilda"}:
        kb.button(text="🚪 Guruhdan chiqarish", callback_data="th:amal:chiq")
        tugmalar_soni += 1
    if not tugmalar_soni:
        return None  # hozir o'qiyotgan guruh yo'q — tugma kerak emas
    kb.adjust(1)
    return kb.as_markup()


def _balans_qatorlari(balans: dict) -> list[str]:
    qiymat = balans.get("balans")
    qatorlar = []
    qarzda = False
    if isinstance(qiymat, (int, float)) and not isinstance(qiymat, bool):
        if qiymat < 0:
            qarzda = True
            qatorlar.append(f"💰 Balans: ❌ Qarzdor — {_pul(-qiymat)}")
        elif qiymat > 0:
            qatorlar.append(f"💰 Balans: ✅ Musbat — {_pul(qiymat)}")
        else:
            qatorlar.append("💰 Balans: 0 so'm")
    elif qiymat is None:
        qatorlar.append("💰 Balans: ma'lumot yo'q")
        qarzda = True
    else:
        qatorlar.append(f"💰 Balans: {_e(qiymat)}")

    holati = balans.get("balans_holati")
    if holati not in (None, ""):
        qatorlar.append(f"📊 Balans holati: {_e(holati)}")
    if balans.get("qarz_sana") and qarzda:
        qatorlar.append(f"📅 Qarzga tushgan sana: {_e(notion_api.sana_ozbekcha(balans['qarz_sana']))}")
    return qatorlar


# =========================================================
# Boshlash va qidirish
# =========================================================

@router.message(F.text == keyboards.TALABA_HOLATI_MATNI)
async def talaba_holati_boshlash(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "🎓 Talaba ismini kiriting (qidirish uchun):", reply_markup=_bekor_klaviaturasi()
    )
    await state.set_state(TalabaHolati.ism_kutish)


@router.message(
    StateFilter(TalabaHolati.ism_kutish, TalabaHolati.talaba_tanlash, TalabaHolati.karta),
    F.text,
    ~F.text.in_(MENYU_MATNLARI),
    ~F.text.startswith("/"),  # /start va boshqa buyruqlar o'z handlerlariga o'tsin
)
async def ism_qidirish(message: Message, state: FSMContext) -> None:
    ism_qismi = (message.text or "").strip()
    if ism_qismi.startswith("/"):
        return
    if len(ism_qismi) < 2:
        await message.answer("❌ Kamida 2 ta harf kiriting:")
        return

    try:
        natijalar = await notion_api.talaba_qidirish(ism_qismi)
    except Exception as xato:
        await message.answer(
            f"❌ Qidiruvda xatolik: {_e(xato)}\n"
            "Notion integratsiyasi Talabalar bazasiga ulanganini tekshiring."
        )
        return

    if not natijalar:
        await message.answer(f"❌ \"{_e(ism_qismi)}\" bo'yicha talaba topilmadi. Boshqa ism yozing:")
        await state.set_state(TalabaHolati.ism_kutish)
        return

    if len(natijalar) == 1:
        await _karta_korsat(message, state, natijalar[0])
        return

    royxat = natijalar[:10]
    await state.update_data(th_qidiruv=royxat)
    qatorlar = ["🔎 Topilgan talabalar:", ""]
    kb = InlineKeyboardBuilder()
    for i, t in enumerate(royxat, start=1):
        qatorlar.append(f"{i}. {_e(t['ism'])}")
        kb.button(text=str(i), callback_data=f"th:t:{i - 1}")
    kb.adjust(5)
    kb.row(*_bekor_klaviaturasi().inline_keyboard[0])
    if len(natijalar) > 10:
        qatorlar.append("")
        qatorlar.append(f"Yana {len(natijalar) - 10} ta bor — ismni aniqroq yozing.")
    await message.answer("\n".join(qatorlar), reply_markup=kb.as_markup())
    await state.set_state(TalabaHolati.talaba_tanlash)


@router.callback_query(TalabaHolati.talaba_tanlash, F.data.startswith("th:t:"))
async def talaba_tanlandi(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    idx = int(callback.data.split(":")[2])
    data = await state.get_data()
    royxat = data.get("th_qidiruv", [])
    if idx >= len(royxat):
        await callback.message.answer("⚠️ Eskirgan tugma. Ismni qaytadan yozing.")
        return
    await _karta_korsat(callback.message, state, royxat[idx])


# =========================================================
# Talaba kartasi
# =========================================================

async def _karta_korsat(target: Message, state: FSMContext, talaba: dict) -> None:
    try:
        yozilishlar, balans = await asyncio.gather(
            notion_api.talaba_yozilishlari(talaba["id"]),
            notion_api.talaba_balansi(talaba["id"]),
        )
    except Exception as xato:
        await target.answer(f"❌ Ma'lumot olishda xatolik: {_e(xato)}")
        return

    joriy = [y for y in yozilishlar if y["holat"] in ("O'qiyabdi", "Ta'tilda")]
    tugagan = [y for y in yozilishlar if y["holat"] == "Tugatdi"]

    davomatlar = await asyncio.gather(
        *[notion_api.yozilish_davomati(y["id"], 5) for y in joriy], return_exceptions=True
    )

    qatorlar = [f"🎓 <b>{_e(talaba['ism'])}</b>", ""]
    qatorlar.extend(_balans_qatorlari(balans))
    qatorlar.append("")

    if joriy:
        qatorlar.append("📚 Guruhlari:")
        for y, davomat in zip(joriy, davomatlar):
            belgi = HOLAT_BELGISI.get(y["holat"], "•")
            qatorlar.append(f"{belgi} <b>{_e(y['guruh_nomi'])}</b> — {_e(y['holat'])}")
            if isinstance(davomat, Exception):
                qatorlar.append("   Davomatni olib bo'lmadi")
            elif not davomat:
                qatorlar.append("   Davomat hali yo'q")
            else:
                qismlar = [
                    f"{_sana_qisqa(d['sana'])} {DAVOMAT_BELGISI.get(d['holat'], '•')}" for d in davomat
                ]
                qatorlar.append("   Oxirgi 5 dars: " + " | ".join(qismlar))
    else:
        qatorlar.append("📚 Hozir o'qiyotgan guruhi yo'q.")

    if tugagan:
        qatorlar.append("")
        qatorlar.append("🔴 Tugatgan: " + ", ".join(_e(y["guruh_nomi"]) for y in tugagan))

    await state.update_data(th_talaba=talaba, th_yozilishlar=yozilishlar)
    await state.set_state(TalabaHolati.karta)
    await target.answer("\n".join(qatorlar), reply_markup=_karta_klaviaturasi(yozilishlar))


# =========================================================
# Amallar: ta'tilga chiqarish / qaytarish / guruhdan chiqarish
# =========================================================

async def _tasdiq_sora(target: Message, state: FSMContext, amal: str, idx: int) -> None:
    data = await state.get_data()
    talaba = data["th_talaba"]
    y = data["th_yozilishlar"][idx]
    await state.update_data(th_amal=amal, th_idx=idx)

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Ha", callback_data="th:ha")
    kb.button(text="❌ Yo'q", callback_data="th:yoq")
    kb.adjust(2)
    await target.answer(
        AMALLAR[amal]["savol"].format(ism=_e(talaba["ism"]), guruh=_e(y["guruh_nomi"])),
        reply_markup=kb.as_markup(),
    )
    await state.set_state(TalabaHolati.tasdiq)


@router.callback_query(TalabaHolati.karta, F.data.startswith("th:amal:"))
async def amal_tanlandi(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    amal = callback.data.split(":")[2]
    if amal not in AMALLAR:
        return
    data = await state.get_data()
    yozilishlar = data["th_yozilishlar"]
    nomzodlar = [i for i, y in enumerate(yozilishlar) if y["holat"] in AMALLAR[amal]["holatlar"]]

    if not nomzodlar:
        await callback.message.answer("⚠️ Bu amal uchun mos guruh yo'q.")
        return
    if len(nomzodlar) == 1:
        await _tasdiq_sora(callback.message, state, amal, nomzodlar[0])
        return

    await state.update_data(th_amal=amal)
    qatorlar = ["Qaysi guruh?", ""]
    kb = InlineKeyboardBuilder()
    for n, i in enumerate(nomzodlar, start=1):
        y = yozilishlar[i]
        qatorlar.append(f"{n}. {_e(y['guruh_nomi'])} — {_e(y['holat'])}")
        kb.button(text=str(n), callback_data=f"th:g:{i}")
    kb.adjust(5)
    kb.row(*_bekor_klaviaturasi().inline_keyboard[0])
    await callback.message.answer("\n".join(qatorlar), reply_markup=kb.as_markup())
    await state.set_state(TalabaHolati.guruh_tanlash)


@router.callback_query(TalabaHolati.guruh_tanlash, F.data.startswith("th:g:"))
async def guruh_tanlandi(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    idx = int(callback.data.split(":")[2])
    data = await state.get_data()
    if idx >= len(data["th_yozilishlar"]):
        await callback.message.answer("⚠️ Eskirgan tugma.")
        return
    await _tasdiq_sora(callback.message, state, data["th_amal"], idx)


@router.callback_query(TalabaHolati.tasdiq, F.data == "th:yoq")
async def tasdiq_yoq(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(TalabaHolati.karta)
    try:
        await callback.message.edit_text("❌ Bekor qilindi. Hech narsa o'zgarmadi.", reply_markup=None)
    except Exception:
        pass


@router.callback_query(TalabaHolati.tasdiq, F.data == "th:ha")
async def tasdiq_ha(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    amal = data["th_amal"]
    idx = data["th_idx"]
    talaba = data["th_talaba"]
    y = data["th_yozilishlar"][idx]

    if y["id"] in _jarayonda:
        await callback.answer("⏳ Jarayonda...")
        return
    _jarayonda.add(y["id"])
    await callback.answer()

    try:
        if amal == "tatil":
            await notion_api.yozilishni_tatilga_chiqarish(y["id"])
        elif amal == "qayt":
            await notion_api.yozilishni_davom_ettirish(y["id"])
        else:
            await notion_api.yozilishni_tugatish(y["id"], "")
    except Exception as xato:
        _jarayonda.discard(y["id"])
        qosimcha = ""
        if getattr(xato, "status", None) == 404:
            qosimcha = "\nIntegratsiya Yozilishlar bazasiga ulanmagan bo'lishi mumkin."
        await callback.message.answer(
            f"❌ Notion xatosi: {_e(xato)}{qosimcha}\nHech narsa o'zgarmadi, qayta urinib ko'rishingiz mumkin."
        )
        return

    _jarayonda.discard(y["id"])
    yozilishlar = data["th_yozilishlar"]
    yozilishlar[idx]["holat"] = AMALLAR[amal]["yangi_holat"]
    await state.update_data(th_yozilishlar=yozilishlar)
    await state.set_state(TalabaHolati.karta)

    natija = AMALLAR[amal]["natija"].format(ism=_e(talaba["ism"]), guruh=_e(y["guruh_nomi"]))
    try:
        await callback.message.edit_text(natija, reply_markup=None)
    except Exception:
        await callback.message.answer(natija)


# =========================================================
# Bekor qilish va eskirgan tugmalar
# =========================================================

@router.callback_query(F.data == "th:bekor")
async def bekor(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    try:
        await callback.message.edit_text("❌ Bekor qilindi.", reply_markup=None)
    except Exception:
        await callback.message.answer("❌ Bekor qilindi.")


@router.callback_query(F.data.startswith("th:"))
async def eskirgan_tugma(callback: CallbackQuery) -> None:
    await callback.answer(
        "Bu tugma eskirgan. 🎓 Talaba holati tugmasini qayta bosing.", show_alert=True
    )
