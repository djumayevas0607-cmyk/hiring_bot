# bot.py
# Aiogram v3 bot: Hiring questionnaire with media prompts and admin controls
# Run with: python bot.py
import asyncio
import json
import re
from datetime import datetime
from typing import List, Dict, Any

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
                           KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from config import BOT_TOKEN, MAIN_ADMIN, JOB_TYPES, STORAGE_DIR

# -------- Simple JSON storage for media and admins --------
MEDIA_FILE = f"{STORAGE_DIR}/media.json"
ADMINS_FILE = f"{STORAGE_DIR}/admins.json"

def null_if_empty(s: str):
    return None if not s else s


def load_json(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Ensure storage dir and files exist
import os
os.makedirs(STORAGE_DIR, exist_ok=True)
if not os.path.exists(MEDIA_FILE):
    save_json(MEDIA_FILE, {
        "intro_video_file_id": null_if_empty(""),
        "voice_prompt_file_id": null_if_empty(""),
        "russian_video_prompt_file_id": null_if_empty("")
    })
if not os.path.exists(ADMINS_FILE):
    save_json(ADMINS_FILE, {"admins": [MAIN_ADMIN]})

def null_if_empty(s: str):
    return None if not s else s

def get_media() -> Dict[str, Any]:
    data = load_json(MEDIA_FILE, {})
    # Guarantee keys
    for key in ["intro_video_file_id", "voice_prompt_file_id", "russian_video_prompt_file_id"]:
        data.setdefault(key, None)
    return data

def get_admins() -> List[int]:
    data = load_json(ADMINS_FILE, {"admins": [MAIN_ADMIN]})
    if MAIN_ADMIN not in data["admins"]:
        data["admins"].append(MAIN_ADMIN)
        save_json(ADMINS_FILE, data)
    return data["admins"]

def is_admin(user_id: int) -> bool:
    return user_id in get_admins()

# -------- FSM --------
class Form(StatesGroup):
    ChooseJob = State()
    AskName = State()
    AskPhone = State()
    AskAddress = State()
    AskBirthday = State()
    AskEducation = State()
    AskExperience = State()
    AskMarital = State()
    WaitVoiceAnswer = State()
    AskRussian = State()
    WaitVideoAnswer = State()
    AskConsent = State()
    AskReference = State()
    AskDuration = State()
    AskOvertime = State()
    AskHealth = State()
    AskWhyLate = State()
    AskWhySteal = State()
    AskWhyGoodBad = State()
    AskPrevSalary = State()
    AskDesiredSalary = State()
    AskCourses = State()
    Done = State()

router = Router()

# Utility keyboards
def inline_from_list(options: List[str], prefix: str) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=opt, callback_data=f"{prefix}:{opt}") ] for opt in options]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def education_kb() -> InlineKeyboardMarkup:
    return inline_from_list(["o'rta", "o'rta maxsus", "oliy"], "edu")

def marital_kb() -> InlineKeyboardMarkup:
    return inline_from_list(["turmush qurganman", "turmush qurmaganman", "ajrashganman"], "marital")

def russian_kb() -> InlineKeyboardMarkup:
    return inline_from_list(["a'lo", "yaxshi", "past", "bilmayman"], "ru")

def yesno_kb() -> InlineKeyboardMarkup:
    return inline_from_list(["ha", "yo'q"], "yn")

def jobs_kb() -> InlineKeyboardMarkup:
    return inline_from_list(JOB_TYPES, "job")

def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Telefon raqamni jo'natish", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True
    )

# Validators
DATE_RE = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")

def valid_date(s: str) -> bool:
    if not DATE_RE.match(s.strip()):
        return False
    try:
        datetime.strptime(s.strip(), "%d.%m.%Y")
        return True
    except ValueError:
        return False

# ------- Start flow -------
@router.message(CommandStart())
async def on_start(message: Message, state: FSMContext, bot: Bot):
    media = get_media()
    # Send intro video if set
    sent_msg = None
    if media.get("intro_video_file_id"):
        try:
            await bot.send_video(chat_id=message.chat.id, video=media["intro_video_file_id"])
        except Exception:
            # ignore sending issues
            pass
    # Send text with job buttons
    text = ("Quyidagi tugmalardan birini tanlang (ish turi):")
    sent_msg = await message.answer(text, reply_markup=jobs_kb())
    # Save this message id to delete later after selection
    await state.update_data(intro_msg_id=sent_msg.message_id)
    await state.set_state(Form.ChooseJob)

# Handle job choice
@router.callback_query(F.data.startswith("job:"), Form.ChooseJob)
async def on_job_choice(call: CallbackQuery, state: FSMContext, bot: Bot):
    job = call.data.split(":", 1)[1]
    data = await state.get_data()
    intro_msg_id = data.get("intro_msg_id")
    # Delete the job text+buttons (video remains)
    if intro_msg_id:
        try:
            await bot.delete_message(chat_id=call.message.chat.id, message_id=intro_msg_id)
        except Exception:
            pass
    await state.update_data(answers={"Ish turi": job})
    await call.answer()
    # Ask for Name-Surname
    await call.message.answer("Ism-familyangizni yozing:")
    await state.set_state(Form.AskName)

@router.message(Form.AskName)
async def ask_phone(message: Message, state: FSMContext):
    if not message.text:
        return
    data = await state.get_data()
    answers = data.get("answers", {})
    answers["Ism-familiya"] = message.text.strip()
    await state.update_data(answers=answers)
    await message.answer("Telefon raqamingizni yozing:\nMisol: +998909998877", reply_markup=phone_kb())
    await state.set_state(Form.AskPhone)

@router.message(Form.AskPhone, F.contact)
async def phone_via_contact(message: Message, state: FSMContext):
    number = message.contact.phone_number
    data = await state.get_data()
    answers = data.get("answers", {})
    answers["Telefon raqami"] = number
    await state.update_data(answers=answers)
    await message.answer("Doimiy yashash manzilingizni yozing (propiska):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Form.AskAddress)

@router.message(Form.AskPhone, F.text)
async def phone_manual(message: Message, state: FSMContext):
    data = await state.get_data()
    answers = data.get("answers", {})
    answers["Telefon raqami"] = message.text.strip()
    await state.update_data(answers=answers)
    await message.answer("Doimiy yashash manzilingizni yozing (propiska):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Form.AskAddress)

@router.message(Form.AskAddress)
async def ask_birthday(message: Message, state: FSMContext):
    if not message.text:
        return
    data = await state.get_data()
    answers = data.get("answers", {})
    answers["Manzil (propiska)"] = message.text.strip()
    await state.update_data(answers=answers)
    await message.answer("O'z tug'ilgan kuningizni 01.01.2000 formatda yozing:")
    await state.set_state(Form.AskBirthday)

@router.message(Form.AskBirthday)
async def ask_education(message: Message, state: FSMContext):
    if not message.text:
        return
    if not valid_date(message.text):
        await message.answer("Tug'ilgan kuningizni 01.01.2000 formatda yozing.")
        return
    data = await state.get_data()
    answers = data.get("answers", {})
    answers["Tug'ilgan sana"] = message.text.strip()
    await state.update_data(answers=answers)
    await message.answer("Ma'lumotingiz:", reply_markup=education_kb())
    await state.set_state(Form.AskEducation)

@router.callback_query(F.data.startswith("edu:"), Form.AskEducation)
async def ask_experience(call: CallbackQuery, state: FSMContext):
    edu = call.data.split(":",1)[1]
    data = await state.get_data()
    answers = data.get("answers", {})
    answers["Ma'lumoti"] = edu
    await state.update_data(answers=answers)
    await call.answer()
    await call.message.answer("Oldin qaysi korxonalarda va qaysi lavozimda ishlagansiz?\nMisol:\n1. Perfect Consulting Group - Sotuv menejeri\n2. Alora - sotuvchi\n3. Ishlamaganman")
    await state.set_state(Form.AskExperience)

@router.message(Form.AskExperience)
async def ask_marital(message: Message, state: FSMContext):
    if not message.text:
        return
    data = await state.get_data()
    answers = data.get("answers", {})
    answers["Ish tajribasi"] = message.text.strip()
    await state.update_data(answers=answers)
    await message.answer("Oila qurganmisiz?", reply_markup=marital_kb())
    await state.set_state(Form.AskMarital)

@router.callback_query(F.data.startswith("marital:"), Form.AskMarital)
async def send_voice_prompt(call: CallbackQuery, state: FSMContext, bot: Bot):
    marital = call.data.split(":",1)[1]
    data = await state.get_data()
    answers = data.get("answers", {})
    answers["Oilaviy holat"] = marital
    await state.update_data(answers=answers)
    await call.answer()
    media = get_media()
    if media.get("voice_prompt_file_id"):
        try:
            await bot.send_voice(chat_id=call.message.chat.id, voice=media["voice_prompt_file_id"])
        except Exception:
            pass
    else:
        await call.message.answer("Iltimos, savolga OVOZ xabari bilan javob yuboring.")
    await state.set_state(Form.WaitVoiceAnswer)

@router.message(Form.WaitVoiceAnswer, F.voice)
async def ask_russian_level(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    answers = data.get("answers", {})

    file_id = message.voice.file_id
    answers["Ovozli javob (file_id)"] = file_id
    await state.update_data(answers=answers)

    
    # 🔹 Продолжаем анкету
    await message.answer("Rus tilini qay darajada bilasiz:", reply_markup=russian_kb())
    await state.set_state(Form.AskRussian)

# If not voice, ignore (bot stays silent by requirement)

@router.callback_query(F.data.startswith("ru:"), Form.AskRussian)
async def send_video_prompt(call: CallbackQuery, state: FSMContext, bot: Bot):
    ru_level = call.data.split(":",1)[1]
    data = await state.get_data()
    answers = data.get("answers", {})
    answers["Rus tili darajasi"] = ru_level
    await state.update_data(answers=answers)
    await call.answer()
    media = get_media()
    if media.get("russian_video_prompt_file_id"):
        try:
            await bot.send_video(chat_id=call.message.chat.id, video=media["russian_video_prompt_file_id"])
        except Exception:
            pass
    else:
        await call.message.answer("Iltimos, VIDEOLI xabar yuboring (video yoki video-note).")
    await state.set_state(Form.WaitVideoAnswer)

@router.message(Form.WaitVideoAnswer, F.video | F.video_note)
async def ask_consent(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    answers = data.get("answers", {})
    file_id = message.video.file_id if message.video else message.video_note.file_id
    answers["Video javob (file_id)"] = file_id
    await state.update_data(answers=answers)

    
    # 🔹 продолжаем анкету
    await message.answer(
        "Oxirgi ish joyingizdan siz haqingizda surishtirishimizga rozimisiz?",
        reply_markup=yesno_kb()
    )
    await state.set_state(Form.AskConsent)


# If not video, ignore (silent)

@router.callback_query(F.data.startswith("yn:"), Form.AskConsent)
async def ask_reference(call: CallbackQuery, state: FSMContext):
    consent = call.data.split(":",1)[1]
    data = await state.get_data()
    answers = data.get("answers", {})
    answers["Surishtirish roziligi"] = consent
    await state.update_data(answers=answers)
    await call.answer()
    await call.message.answer("Oxirgi ish joyingizdan kim sizga tavsiya xati bera oladi, nomi, ishlash joyi, lavozimi, telefon raqami:\nMisol: Direktor - Malika Akramovna - Nona collection - +998909998877")
    await state.set_state(Form.AskReference)

@router.message(Form.AskReference)
async def ask_duration(message: Message, state: FSMContext):
    data = await state.get_data()
    answers = data.get("answers", {})
    answers["Tavsiyanoma beruvchi"] = message.text.strip()
    await state.update_data(answers=answers)
    await message.answer("Bizning korxonada qancha muddat ishlamoqchisiz?")
    await state.set_state(Form.AskDuration)

@router.message(Form.AskDuration)
async def ask_overtime(message: Message, state: FSMContext):
    data = await state.get_data()
    answers = data.get("answers", {})
    answers["Qancha muddat ishlamoqchi"] = message.text.strip()
    await state.update_data(answers=answers)
    await message.answer("Korxonada ishdan keyin xam qolib ishlash kerak bo‘lib qolsa ishlaysizmi?")
    await state.set_state(Form.AskOvertime)

@router.message(Form.AskOvertime)
async def ask_health(message: Message, state: FSMContext):
    data = await state.get_data()
    answers = data.get("answers", {})
    answers["Ishdan keyin qolishga rozilik"] = message.text.strip()
    await state.update_data(answers=answers)
    await message.answer("Sog‘ligingizda muammo yo‘qmi?")
    await state.set_state(Form.AskHealth)

@router.message(Form.AskHealth)
async def ask_whylate(message: Message, state: FSMContext):
    data = await state.get_data()
    answers = data.get("answers", {})
    answers["Sog'liq holati"] = message.text.strip()
    await state.update_data(answers=answers)
    await message.answer("Nima uchun ayrim odamlar ishga kech kelishadi?")
    await state.set_state(Form.AskWhyLate)

@router.message(Form.AskWhyLate)
async def ask_whysteal(message: Message, state: FSMContext):
    data = await state.get_data()
    answers = data.get("answers", {})
    answers["Nega kech kelishadi"] = message.text.strip()
    await state.update_data(answers=answers)
    await message.answer("Nima uchun ayrim insonlar o'g'rilik qilishadi?")
    await state.set_state(Form.AskWhySteal)

@router.message(Form.AskWhySteal)
async def ask_whygoodbad(message: Message, state: FSMContext):
    data = await state.get_data()
    answers = data.get("answers", {})
    answers["Nega o'g'rilik qilishadi"] = message.text.strip()
    await state.update_data(answers=answers)
    await message.answer("Nima uchun ayrim ishchilar yaxshi ishlashadi, ayrimlari yomon? Bunga sabab nima?")
    await state.set_state(Form.AskWhyGoodBad)

@router.message(Form.AskWhyGoodBad)
async def ask_prev_salary(message: Message, state: FSMContext):
    data = await state.get_data()
    answers = data.get("answers", {})
    answers["Yaxshi-yomon ish sababi"] = message.text.strip()
    await state.update_data(answers=answers)
    await message.answer("Oldingi ishxonangizda qancha maoshga ishlgansiz?")
    await state.set_state(Form.AskPrevSalary)

@router.message(Form.AskPrevSalary)
async def ask_desired_salary(message: Message, state: FSMContext):
    data = await state.get_data()
    answers = data.get("answers", {})
    answers["Oldingi maosh"] = message.text.strip()
    await state.update_data(answers=answers)
    await message.answer("Bizning ishxonamizda qancha maoshga ishlamoqchisiz?")
    await state.set_state(Form.AskDesiredSalary)

@router.message(Form.AskDesiredSalary)
async def ask_courses(message: Message, state: FSMContext):
    data = await state.get_data()
    answers = data.get("answers", {})
    answers["Kutilgan maosh"] = message.text.strip()
    await state.update_data(answers=answers)
    await message.answer("Qanday kurslarda o’qigansiz?")
    await state.set_state(Form.AskCourses)

@router.message(Form.AskCourses)
async def finish_form(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    answers = data.get("answers", {})
    answers["Kurslar"] = message.text.strip()
    # Compose summary
    lines = [f"📝 Yangi ariza #{message.from_user.id}"]
    lines.append(f"F.I.Sh: {answers.get('Ism-familiya','')}")
    lines.append(f"Ish turi: {answers.get('Ish turi','')}")
    for k, v in answers.items():
        if k in ["Ism-familiya", "Ish turi"]:
            continue
        lines.append(f"{k}: {v}")
    text = "\n".join(lines)
    # Send to all admins with voice and video
    for admin_id in get_admins():
        try:
            # Отправляем текст анкеты
            await bot.send_message(chat_id=admin_id, text=text)

            # 🔹 Отправляем голос пользователя, если есть
            if "Ovozli javob (file_id)" in answers:
                await bot.send_voice(chat_id=admin_id, voice=answers["Ovozli javob (file_id)"])

            # 🔹 Отправляем видео пользователя, если есть
            if "Video javob (file_id)" in answers:
                await bot.send_video(chat_id=admin_id, video=answers["Video javob (file_id)"])

        except Exception:
            pass

    await message.answer("Ma'lumotlaringiz qabul qilindi. Tez orada xabarini beramiz!")
    await state.set_state(Form.Done)
    await state.clear()

# ------------- Admin commands -------------
@router.message(Command("set_intro_video"))
async def set_intro_video(msg: Message, bot: Bot):
    if not is_admin(msg.from_user.id):
        return
    if not msg.reply_to_message or not (msg.reply_to_message.video or msg.reply_to_message.video_note):
        await msg.answer("Ushbu buyruqni video xabariga javoban yuboring (reply).")
        return
    file_id = (msg.reply_to_message.video.file_id if msg.reply_to_message.video 
               else msg.reply_to_message.video_note.file_id)
    media = get_media()
    media["intro_video_file_id"] = file_id
    save_json(MEDIA_FILE, media)
    await msg.answer("Intro video yangilandi. ✅")

@router.message(Command("set_voice_prompt"))
async def set_voice_prompt(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    if not msg.reply_to_message or not msg.reply_to_message.voice:
        await msg.answer("Ushbu buyruqni OVOZ xabariga javoban yuboring (reply).")
        return
    file_id = msg.reply_to_message.voice.file_id
    media = get_media()
    media["voice_prompt_file_id"] = file_id
    save_json(MEDIA_FILE, media)
    await msg.answer("Ovozli savol yangilandi. ✅")

@router.message(Command("set_russian_video"))
async def set_russian_video(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    if not msg.reply_to_message or not (msg.reply_to_message.video or msg.reply_to_message.video_note):
        await msg.answer("Ushbu buyruqni video xabariga javoban yuboring (reply).")
        return
    file_id = (msg.reply_to_message.video.file_id if msg.reply_to_message.video 
               else msg.reply_to_message.video_note.file_id)
    media = get_media()
    media["russian_video_prompt_file_id"] = file_id
    save_json(MEDIA_FILE, media)
    await msg.answer("Rus tili uchun video savol yangilandi. ✅")

@router.message(Command("add_admin"))
async def add_admin(msg: Message):
    if msg.from_user.id != MAIN_ADMIN:
        return
    parts = msg.text.strip().split()
    if len(parts) != 2 or not parts[1].isdigit():
        await msg.answer("Foydalanish: /add_admin 123456789")
        return
    uid = int(parts[1])
    data = load_json(ADMINS_FILE, {"admins": [MAIN_ADMIN]})
    if uid not in data["admins"]:
        data["admins"].append(uid)
        save_json(ADMINS_FILE, data)
    await msg.answer(f"Admin qo'shildi: {uid} ✅")

@router.message(Command("remove_admin"))
async def remove_admin(msg: Message):
    if msg.from_user.id != MAIN_ADMIN:
        return
    parts = msg.text.strip().split()
    if len(parts) != 2 or not parts[1].isdigit():
        await msg.answer("Foydalanish: /remove_admin 123456789")
        return
    uid = int(parts[1])
    data = load_json(ADMINS_FILE, {"admins": [MAIN_ADMIN]})
    if uid in data["admins"] and uid != MAIN_ADMIN:
        data["admins"].remove(uid)
        save_json(ADMINS_FILE, data)
        await msg.answer(f"Admin o'chirildi: {uid} ✅")
    else:
        await msg.answer("Bu foydalanuvchini o'chirish mumkin emas.")

@router.message(Command("cancel"))
async def cancel(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("Bekor qilindi. /start dan qayta boshlang.", reply_markup=ReplyKeyboardRemove())


# main.py
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.bot import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from bot import router   # твой router из bot.py
from config import BOT_TOKEN

# --- Bot ---
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)

# --- Dispatcher ---
dp = Dispatcher()
dp.include_router(router)

# --- Webhook config ---
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "https://ТВОЁ-ПРИЛОЖЕНИЕ.koyeb.app")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# --- Startup / Shutdown ---
async def on_startup(app: web.Application):
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(WEBHOOK_URL)
    print("Webhook установлен:", WEBHOOK_URL)

async def on_shutdown(app: web.Application):
    await bot.session.close()
    print("Bot остановлен")

# --- Main ---
def main():
    app = web.Application()

    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    port = int(os.getenv("PORT", 8080))
    web.run_app(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
