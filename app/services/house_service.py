from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.location import Apartment, House, HouseEntrance
from app.models.ticket import Ticket, TicketPriority, TicketStatus
from app.repositories.house_repository import HouseRepository
from app.schemas.location import (
    ApartmentCreate,
    ApartmentGenerateRequest,
    ApartmentUpdate,
    HouseCreate,
    HouseEntranceCreate,
    HouseEntranceUpdate,
    HouseUpdate,
    HouseWithStructureCreateRequest,
)


class HouseService:
    def __init__(self, db: Session):
        self.db = db
        self.house_repo = HouseRepository(db)

    def _get_house_or_404(self, house_id: int) -> House:
        house = self.house_repo.get_by_id(house_id)
        if not house:
            raise HTTPException(status_code=404, detail="House not found")
        return house

    def _get_entrance_or_404(self, entrance_id: int) -> HouseEntrance:
        entrance = (
            self.db.query(HouseEntrance)
            .filter(HouseEntrance.id == entrance_id)
            .first()
        )
        if not entrance:
            raise HTTPException(status_code=404, detail="Entrance not found")
        return entrance

    def _get_apartment_or_404(self, apartment_id: int) -> Apartment:
        apartment = (
            self.db.query(Apartment)
            .filter(Apartment.id == apartment_id)
            .first()
        )
        if not apartment:
            raise HTTPException(status_code=404, detail="Apartment not found")
        return apartment

    def _recalc_entrance_stats(self, entrance: HouseEntrance) -> None:
        apartments = (
            self.db.query(Apartment)
            .filter(Apartment.entrance_id == entrance.id)
            .all()
        )

        entrance.apartments_count = len(apartments)
        entrance.floors_count = max((a.floor_number for a in apartments), default=0)

    def _ensure_house_address_unique(self, address: str) -> None:
        existing = (
            self.db.query(House)
            .filter(House.address == address)
            .first()
        )
        if existing:
            raise HTTPException(status_code=409, detail="House with this address already exists")

    def _enrich_apartment_issue_meta(self, house: House) -> None:
        active_tickets = (
            self.db.query(Ticket)
            .filter(
                Ticket.house_id == house.id,
                Ticket.status.notin_([TicketStatus.DONE, TicketStatus.CLOSED, TicketStatus.CANCELED]),
            )
            .all()
        )

        by_apartment_id: dict[int, list[Ticket]] = {}
        by_apartment_number: dict[str, list[Ticket]] = {}
        priority_rank = {
            TicketPriority.LOW.value: 1,
            TicketPriority.NORMAL.value: 2,
            TicketPriority.HIGH.value: 3,
            TicketPriority.EMERGENCY.value: 4,
        }

        for ticket in active_tickets:
            if ticket.apartment_id:
                by_apartment_id.setdefault(ticket.apartment_id, []).append(ticket)
            elif ticket.apartment:
                by_apartment_number.setdefault(str(ticket.apartment), []).append(ticket)

        for entrance in house.entrances:
            for apartment in entrance.apartments:
                tickets = list(by_apartment_id.get(apartment.id, []))
                tickets.extend(by_apartment_number.get(str(apartment.apartment_number), []))

                apartment.unresolved_tickets_count = len({ticket.id for ticket in tickets})

                highest_priority = None
                highest_rank = 0
                for ticket in tickets:
                    value = ticket.priority.value if hasattr(ticket.priority, "value") else str(ticket.priority or "")
                    rank = priority_rank.get(value, 0)
                    if rank > highest_rank:
                        highest_rank = rank
                        highest_priority = value or None

                apartment.highest_unresolved_priority = highest_priority

    def create_house(self, house_in: HouseCreate):
        self._ensure_house_address_unique(house_in.address)
        return self.house_repo.create(house_in.model_dump())

    def create_house_with_structure(self, payload: HouseWithStructureCreateRequest):
        self._ensure_house_address_unique(payload.address)

        seen_numbers = set()
        for spec in payload.entrances:
            if spec.number in seen_numbers:
                raise HTTPException(status_code=400, detail=f"Duplicate entrance number: {spec.number}")
            seen_numbers.add(spec.number)

        house = House(city=payload.city, address=payload.address)
        self.db.add(house)
        self.db.flush()

        next_apartment_number = 1

        for spec in payload.entrances:
            entrance = HouseEntrance(
                house_id=house.id,
                number=spec.number,
                floors_count=0,
                apartments_count=0,
                is_active=spec.is_active,
            )
            self.db.add(entrance)
            self.db.flush()

            current_number = spec.start_number if spec.start_number is not None else next_apartment_number

            for floor_number in range(spec.start_floor, spec.start_floor + spec.floors_count):
                for _ in range(spec.apartments_per_floor):
                    apartment_number = str(current_number)

                    exists = (
                        self.db.query(Apartment)
                        .filter(
                            Apartment.house_id == house.id,
                            Apartment.apartment_number == apartment_number
                        )
                        .first()
                    )
                    if exists:
                        raise HTTPException(
                            status_code=409,
                            detail=f"Apartment number already exists in this house: {apartment_number}"
                        )

                    apartment = Apartment(
                        house_id=house.id,
                        entrance_id=entrance.id,
                        floor_number=floor_number,
                        apartment_number=apartment_number,
                        rooms_count=spec.rooms_count,
                        is_active=True,
                    )
                    self.db.add(apartment)
                    current_number += 1

            next_apartment_number = max(next_apartment_number, current_number)
            self.db.flush()
            self._recalc_entrance_stats(entrance)

        self.db.commit()
        self.db.refresh(house)

        return self.get_house_structure(house.id)

    def get_all_houses(self):
        return self.house_repo.get_all()

    def update_house(self, house_id: int, house_in: HouseUpdate):
        return self.house_repo.update(house_id, house_in.model_dump())

    def delete_house(self, house_id: int):
        return self.house_repo.delete(house_id)

    def get_house_structure(self, house_id: int):
        house = self._get_house_or_404(house_id)

        entrances_sorted = sorted(house.entrances, key=lambda x: x.number)
        for entrance in entrances_sorted:
            entrance.apartments = sorted(
                entrance.apartments,
                key=lambda x: (x.floor_number, str(x.apartment_number))
            )

        house.entrances = entrances_sorted
        self._enrich_apartment_issue_meta(house)
        return house

    def list_entrances(self, house_id: int):
        self._get_house_or_404(house_id)

        return (
            self.db.query(HouseEntrance)
            .filter(HouseEntrance.house_id == house_id)
            .order_by(HouseEntrance.number.asc())
            .all()
        )

    def create_entrance(self, house_id: int, payload: HouseEntranceCreate):
        self._get_house_or_404(house_id)

        exists = (
            self.db.query(HouseEntrance)
            .filter(
                HouseEntrance.house_id == house_id,
                HouseEntrance.number == payload.number
            )
            .first()
        )
        if exists:
            raise HTTPException(status_code=409, detail="Entrance with this number already exists")

        obj = HouseEntrance(
            house_id=house_id,
            **payload.model_dump()
        )
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update_entrance(self, entrance_id: int, payload: HouseEntranceUpdate):
        entrance = self._get_entrance_or_404(entrance_id)

        data = payload.model_dump(exclude_unset=True)

        if "number" in data:
            exists = (
                self.db.query(HouseEntrance)
                .filter(
                    HouseEntrance.house_id == entrance.house_id,
                    HouseEntrance.number == data["number"],
                    HouseEntrance.id != entrance.id
                )
                .first()
            )
            if exists:
                raise HTTPException(status_code=409, detail="Entrance with this number already exists")

        for key, value in data.items():
            setattr(entrance, key, value)

        self.db.commit()
        self.db.refresh(entrance)
        return entrance

    def delete_entrance(self, entrance_id: int):
        entrance = self._get_entrance_or_404(entrance_id)

        if entrance.apartments:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete entrance while it contains apartments"
            )

        self.db.delete(entrance)
        self.db.commit()
        return {"status": "deleted"}

    def list_apartments_for_house(self, house_id: int):
        self._get_house_or_404(house_id)

        return (
            self.db.query(Apartment)
            .filter(Apartment.house_id == house_id)
            .order_by(Apartment.entrance_id.asc(), Apartment.floor_number.asc(), Apartment.apartment_number.asc())
            .all()
        )

    def list_apartments_for_entrance(self, entrance_id: int):
        self._get_entrance_or_404(entrance_id)

        return (
            self.db.query(Apartment)
            .filter(Apartment.entrance_id == entrance_id)
            .order_by(Apartment.floor_number.asc(), Apartment.apartment_number.asc())
            .all()
        )

    def create_apartment(self, entrance_id: int, payload: ApartmentCreate):
        entrance = self._get_entrance_or_404(entrance_id)

        exists = (
            self.db.query(Apartment)
            .filter(
                Apartment.house_id == entrance.house_id,
                Apartment.apartment_number == payload.apartment_number
            )
            .first()
        )
        if exists:
            raise HTTPException(status_code=409, detail="Apartment number already exists in this house")

        obj = Apartment(
            house_id=entrance.house_id,
            entrance_id=entrance.id,
            **payload.model_dump()
        )
        self.db.add(obj)
        self.db.flush()

        self._recalc_entrance_stats(entrance)

        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update_apartment(self, apartment_id: int, payload: ApartmentUpdate):
        apartment = self._get_apartment_or_404(apartment_id)
        data = payload.model_dump(exclude_unset=True)

        new_number = data.get("apartment_number")
        if new_number is not None:
            exists = (
                self.db.query(Apartment)
                .filter(
                    Apartment.house_id == apartment.house_id,
                    Apartment.apartment_number == new_number,
                    Apartment.id != apartment.id
                )
                .first()
            )
            if exists:
                raise HTTPException(status_code=409, detail="Apartment number already exists in this house")

        for key, value in data.items():
            setattr(apartment, key, value)

        self._recalc_entrance_stats(apartment.entrance)

        self.db.commit()
        self.db.refresh(apartment)
        return apartment

    def delete_apartment(self, apartment_id: int):
        apartment = self._get_apartment_or_404(apartment_id)

        if apartment.residents:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete apartment with linked residents"
            )

        if apartment.tickets:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete apartment with linked tickets"
            )

        entrance = apartment.entrance

        self.db.delete(apartment)
        self.db.flush()

        self._recalc_entrance_stats(entrance)

        self.db.commit()
        return {"status": "deleted"}

    def generate_apartments(self, entrance_id: int, payload: ApartmentGenerateRequest):
        entrance = self._get_entrance_or_404(entrance_id)

        generated_numbers = []
        current_number = payload.start_number

        for _floor in range(payload.start_floor, payload.start_floor + payload.floors_count):
            for _ in range(payload.apartments_per_floor):
                generated_numbers.append(str(current_number))
                current_number += 1

        existing = (
            self.db.query(Apartment)
            .filter(
                Apartment.house_id == entrance.house_id,
                Apartment.apartment_number.in_(generated_numbers)
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Apartment number already exists in this house: {existing.apartment_number}"
            )

        created = []
        current_number = payload.start_number

        for floor_number in range(payload.start_floor, payload.start_floor + payload.floors_count):
            for _ in range(payload.apartments_per_floor):
                obj = Apartment(
                    house_id=entrance.house_id,
                    entrance_id=entrance.id,
                    floor_number=floor_number,
                    apartment_number=str(current_number),
                    rooms_count=payload.rooms_count,
                    is_active=True,
                )
                self.db.add(obj)
                created.append(obj)
                current_number += 1

        self.db.flush()
        self._recalc_entrance_stats(entrance)
        self.db.commit()

        for obj in created:
            self.db.refresh(obj)

        return created
