from aiogram import Router
from . import start, other

router = Router()
router.include_router(start.router)
router.include_router(other.router)
