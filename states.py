from aiogram.fsm.state import State, StatesGroup


class TalabaQoshish(StatesGroup):
    turi_tanlash = State()        # Yangi yoki mavjud talaba
    ism_kiritish = State()        # Yangi talaba: ism kiritish
    telegram_id_kutish = State()  # Yangi talaba: Telegram ID (forward/matn/o'tkazish)
    mavjud_qidirish = State()     # Mavjud talaba: ism bo'yicha qidiruv matni
    mavjud_tanlash = State()      # Mavjud talaba: qidiruv natijalaridan tanlash
    ustoz_tanlash = State()       # Ustoz tugmalari
    guruh_tanlash = State()       # Guruh tugmalari
    sana_kutish = State()         # Boshlagan sana (tugma yoki qo'lda)
    tolov_kutish = State()        # Dastlabki to'lov (faqat yangi talaba)
    yana_guruh = State()          # "Yana guruhga yozamizmi?"
    xulosa_tasdiq = State()       # Yakuniy tasdiqlash
    keyingi_talaba = State()      # Saqlangandan keyin "Yana talaba qo'shamizmi?"
