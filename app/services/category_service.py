from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.profanity import ensure_clean_text
from app.models.category import Category
from app.models.ticket import Ticket
from app.repositories.category_repository import CategoryRepository
from app.schemas.category import CategoryCreate


VALID_CATEGORY_TYPES = {"problem", "location"}


class CategoryService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CategoryRepository(db)

    def _normalize_category_type(self, value: str | None) -> str:
        category_type = (value or "problem").strip().lower()
        if category_type in {"place", "where"}:
            category_type = "location"
        if category_type not in VALID_CATEGORY_TYPES:
            raise HTTPException(status_code=400, detail="Unsupported category type")
        return category_type

    def create_category(self, category_in: CategoryCreate):
        name = (category_in.name or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Название категории обязательно")

        ensure_clean_text(name)
        category_type = self._normalize_category_type(category_in.category_type)

        existing = (
            self.db.query(Category)
            .filter(Category.name.ilike(name), Category.category_type == category_type)
            .first()
        )
        if existing:
            raise HTTPException(status_code=400, detail="Категория с таким названием уже существует")

        return self.repo.create({"name": name, "category_type": category_type})

    def get_all(self, category_type: str | None = "problem"):
        requested_type = (category_type or "problem").strip().lower()
        if requested_type == "all":
            return self.db.query(Category).order_by(Category.category_type.asc(), Category.name.asc()).all()
        normalized_type = self._normalize_category_type(requested_type)
        return (
            self.db.query(Category)
            .filter(Category.category_type == normalized_type)
            .order_by(Category.name.asc())
            .all()
        )

    def delete_category(self, category_id: int):
        category = self.repo.get_by_id(category_id)
        if not category:
            raise HTTPException(status_code=404, detail="Категория не найдена")

        self.db.query(Ticket).filter(Ticket.category_id == category_id).update(
            {Ticket.category_id: None},
            synchronize_session=False,
        )
        self.db.query(Ticket).filter(Ticket.place_category_id == category_id).update(
            {Ticket.place_category_id: None},
            synchronize_session=False,
        )
        self.db.delete(category)
        self.db.commit()
        return {"status": "ok"}
