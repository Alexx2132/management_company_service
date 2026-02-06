from fastapi import APIRouter
from app.api.v1.endpoints import auth, housing, tickets, announcements, categories, users # <-- Добавили users в импорт

router = APIRouter()

# Подключаем роутеры из разных файлов
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(users.router, prefix="/users", tags=["users"]) # <-- Подключили новый файл
router.include_router(housing.router, prefix="/houses", tags=["housing"])
router.include_router(tickets.router, prefix="/tickets", tags=["tickets"])
router.include_router(announcements.router, prefix="/announcements", tags=["announcements"])
router.include_router(categories.router, prefix="/categories", tags=["categories"])
