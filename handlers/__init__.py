# handlers/__init__.py
from aiogram import Router

from .start import router as start_router
from .other import router as other_router
# сюда добавляй все остальные файлы, где есть router

router = Router()
router.include_router(start_router)
router.include_router(other_router)
