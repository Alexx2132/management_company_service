from sqlalchemy.orm import Session
from app.repositories.house_repository import HouseRepository
from app.schemas.location import HouseCreate
from app.schemas.location import HouseUpdate

class HouseService:
    def __init__(self, db: Session):
        self.house_repo = HouseRepository(db)

    def create_house(self, house_in: HouseCreate):
        # Здесь можно добавить проверку, нет ли уже такого адреса
        return self.house_repo.create(house_in.model_dump())

    def get_all_houses(self):
        return self.house_repo.get_all()

    def update_house(self, house_id: int, house_in: HouseUpdate):
        return self.house_repo.update(house_id, house_in.model_dump())

    def delete_house(self, house_id: int):
        return self.house_repo.delete(house_id)
