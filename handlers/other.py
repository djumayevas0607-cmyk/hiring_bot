from aiogram import Router, types

router = Router()

@router.message()
async def echo(message: types.Message):
    # Здесь твоя логика для всех остальных сообщений
    await message.answer(f"Ты написал: {message.text}")
