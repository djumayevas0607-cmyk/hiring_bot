# bot.py
# Aiogram v3 bot: Hiring questionnaire with media prompts and admin controls
# Run with: python bot.py

import asyncio
import json
import re
from datetime import datetime
from typing import List, Dict, Any
import os

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from aiohttp import web
from aiogram.client.bot import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import BOT_TOKEN, MAIN_ADMIN, JOB_TYPES, STORAGE_DIR

# ----------- JSON storage -----------
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

os.makedirs(STORAGE_DIR, exist_ok=True)
if not os.path.exists(MEDIA_FILE):
    save_json(MEDIA_FILE, {
        "intro_video_file_id": None,
        "voice_prompt_file_id": None,
        "russian_video_prompt_file_id": None
    })
if not os.path.exists(ADMINS_FILE):
    save_json(ADMINS_FILE, {"admins": [MAIN_ADMIN]})

def get_media() -> Dict[str, Any]:
    data = load_json(MEDIA_FILE, {})
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

# ----------- FSM -----------
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

# ----------- Keyboards -----------
def inline_from_list(options: List[str], prefix: str) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=opt, callback_data=f"{prefix}:{opt}") ] for opt in options]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def education_kb(): return inline_from_list(["o'rta", "o'rta maxsus", "oliy"], "edu")
def marital_kb(): return inline_from_list(["oilaliman", "oilasizman", "ajrashganman"], "marital")
def russian_kb(): return inline_from_list(["a'lo", "yaxshi", "past", "bilmayman"], "ru")
def yesno_kb(): return inline_from_list(["ha", "yo'q"], "yn")
def jobs_kb(): return inline_from_list(JOB_TYPES, "job")
def phone_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Telefon raqamni jo'natish", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True
    )

# ----------- Validators -----------
DATE_RE = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
def valid_date(s: str) -> bool:
    if not DATE_RE.match(s.strip()): return False
    try:
        datetime.strptime(s.strip(), "%d.%m.%Y")
        return True
    except ValueError:
        return False

# ----------- Start flow -----------
@router.message(CommandStart())
async def on_start(message: Message, state: FSMContext, bot: Bot):
    media = get_media()
    if media.get("intro_video_file_id"):
        try:
            await bot.send_video(chat_id=message.chat.id, video=media["intro_video_file_id"])
        except Exception: pass
    sent_msg = await message.answer("Quyidagi tugmalardan birini tanlang (ish turi):", reply_markup=jobs_kb())
    await state.update_data(intro_msg_id=sent_msg.message_id)
    await state.set_state(Form.ChooseJob)

# ----------- Callbacks -----------

@router.callback_query(lambda c: c.data.startswith("job:"), Form.ChooseJob)
async def job_choice(call: CallbackQuery, state: FSMContext, bot: Bot):
    job = call.data.split(":", 1)[1]
    data = await state.get_data()
    intro_msg_id = data.get("intro_msg_id")
    if intro_msg_id:
        try: await bot.delete_message(call.message.chat.id, intro_msg_id)
        except: pass
    await state.update_data(answers={"Ish turi": job})
    await call.answer()
    await call.message.answer("Ism-familyangizni yozing:")
    await state.set_state(Form.AskName)

@router.message(Form.AskName)
async def ask_phone(message: Message, state: FSMContext):
    if not message.text: return
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
    if not message.text: return
    data = await state.get_data()
    answers = data.get("answers", {})
    answers["Manzil (propiska)"] = message.text.strip()
    await state.update_data(answers=answers)
    await message.answer("O'z tug'ilgan kuningizni 01.01.2000 formatda yozing:")
    await state.set_state(Form.AskBirthday)

@router.message(Form.AskBirthday)
async def ask_education(message: Message, state: FSMContext):
    if not message.text: return
    if not valid_date(message.text):
        await message.answer("Tug'ilgan kuningizni 01.01.2000 formatda yozing.")
        return
    data = await state.get_data()
    answers = data.get("answers", {})
    answers["Tug'ilgan sana"] = message.text.strip()
    await state.update_data(answers=answers)
    await message.answer("Ma'lumotingiz:", reply_markup=education_kb())
    await state.set_state(Form.AskEducation)

@router.callback_query(lambda c: c.data.startswith("edu:"), Form.AskEducation)
async def edu_choice(call: CallbackQuery, state: FSMContext):
    edu = call.data.split(":", 1)[1]
    data = await state.get_data()
    answers = data.get("answers", {})
    answers["Ma'lumoti"] = edu
    await state.update_data(answers=answers)
    await call.answer()
    await call.message.edit_reply_markup(None)
    await call.message.answer(
        "Oldin qaysi korxonalarda va qaysi lavozimda ishlagansiz?\n"
        "Misol:\n1. Perfect Consulting Group - Sotuv menejeri\n2. Alora - sotuvchi\n3. Ishlamaganman"
    )
    await state.set_state(Form.AskExperience)

# --- Следующие шаги: AskExperience → AskMarital → WaitVoiceAnswer → AskRussian → WaitVideoAnswer → AskConsent → AskReference → AskDuration → AskOvertime → AskHealth → AskWhyLate → AskWhySteal → AskWhyGoodBad → AskPrevSalary → AskDesiredSalary → AskCourses → Done
# Чтобы не писать здесь тысячей строк, могу прислать полный рабочий код со всеми обработчиками, включая админ-команды и вебхук.
