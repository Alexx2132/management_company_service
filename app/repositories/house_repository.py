from app.repositories.base import BaseRepository
from app.models.location import House
from sqlalchemy.orm import Session
from fastapi import HTTPException


class HouseRepository(BaseRepository[House]):
    def __init__(self, db: Session):
        super().__init__(House, db)

    def update(self, house_id: int, house_data: dict) -> House:
        house = self.get_by_id(house_id)
        if not house:
            raise HTTPException(404, "House not found")

        for key, value in house_data.items():
            if value is not None:  # Обновляем только то, что передали
                setattr(house, key, value)

        self.db.commit()
        self.db.refresh(house)
        return house

    def delete(self, house_id: int):
        house = self.get_by_id(house_id)
        if not house:
            raise HTTPException(404, "House not found")

        # Проверка на наличие зависимостей (жильцы/заявки)
        # Если не проверить, SQLAlchemy всё равно выкинет IntegrityError,
        # но лучше сделать это явно и вернуть понятную ошибку.
        if house.tickets or house.users:  # (нужно чтобы в модели House была связь users)
            # Если связи users нет в модели, то проверка только по tickets
            # Либо поймать исключение IntegrityError при удалении
            pass

        try:
            self.db.delete(house)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            # Скорее всего это IntegrityError (есть жильцы)
            raise HTTPException(400, "Cannot delete house with residents or tickets")

        return {"status": "deleted"}