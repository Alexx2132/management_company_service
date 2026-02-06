from sqlalchemy.orm import Session
from app.repositories.category_repository import CategoryRepository
from app.schemas.category import CategoryCreate

class CategoryService:
    def __init__(self, db: Session):
        self.repo = CategoryRepository(db)

    def create_category(self, category_in: CategoryCreate):

        return self.repo.create(category_in.model_dump())

    def get_all(self):
        return self.repo.get_all()
