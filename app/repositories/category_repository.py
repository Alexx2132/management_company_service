from sqlalchemy.orm import Session
from app.repositories.base import BaseRepository
from app.models.category import Category

class CategoryRepository(BaseRepository[Category]):
    def __init__(self, db: Session):
        super().__init__(Category, db)
