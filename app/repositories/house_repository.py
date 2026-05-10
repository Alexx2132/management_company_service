from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.location import House
from app.repositories.base import BaseRepository


class HouseRepository(BaseRepository[House]):
    def __init__(self, db: Session):
        super().__init__(House, db)

    def update(self, house_id: int, house_data: dict) -> House:
        house = self.get_by_id(house_id)
        if not house:
            raise HTTPException(404, "House not found")

        for key, value in house_data.items():
            if value is not None:
                setattr(house, key, value)

        self.db.commit()
        self.db.refresh(house)
        return house

    def delete(self, house_id: int):
        house = self.get_by_id(house_id)
        if not house:
            raise HTTPException(404, "House not found")

        has_dependencies = any([
            bool(house.tickets),
            bool(house.users),
            bool(house.events),
            bool(house.emergency_contacts),
            bool(house.schedules),
            bool(house.entrances),
            bool(house.apartments),
        ])

        if has_dependencies:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete house with linked users, tickets, entrances, apartments or house info"
            )

        self.db.delete(house)
        self.db.commit()
        return {"status": "deleted"}