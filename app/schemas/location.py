from datetime import datetime

from pydantic import BaseModel, Field


class HouseBase(BaseModel):
    city: str = "Default City"
    address: str


class HouseCreate(HouseBase):
    pass


class HouseUpdate(BaseModel):
    city: str | None = None
    address: str | None = None


class HouseResponse(HouseBase):
    id: int

    class Config:
        from_attributes = True


class HouseEntranceBase(BaseModel):
    number: int = Field(..., ge=1)
    floors_count: int = Field(default=0, ge=0)
    apartments_count: int = Field(default=0, ge=0)
    is_active: bool = True


class HouseEntranceCreate(HouseEntranceBase):
    pass


class HouseEntranceUpdate(BaseModel):
    number: int | None = Field(default=None, ge=1)
    floors_count: int | None = Field(default=None, ge=0)
    apartments_count: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class HouseEntranceResponse(HouseEntranceBase):
    id: int
    house_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ApartmentBase(BaseModel):
    floor_number: int = Field(..., ge=1)
    apartment_number: str
    rooms_count: int | None = Field(default=None, ge=1)
    is_active: bool = True


class ApartmentCreate(ApartmentBase):
    pass


class ApartmentUpdate(BaseModel):
    floor_number: int | None = Field(default=None, ge=1)
    apartment_number: str | None = None
    rooms_count: int | None = Field(default=None, ge=1)
    is_active: bool | None = None


class ApartmentResponse(ApartmentBase):
    id: int
    house_id: int
    entrance_id: int
    created_at: datetime
    unresolved_tickets_count: int = 0
    highest_unresolved_priority: str | None = None

    class Config:
        from_attributes = True


class ApartmentGenerateRequest(BaseModel):
    floors_count: int = Field(..., ge=1)
    apartments_per_floor: int = Field(..., ge=1)
    start_number: int = Field(default=1, ge=1)
    start_floor: int = Field(default=1, ge=1)
    rooms_count: int | None = Field(default=None, ge=1)


class HouseEntranceWithApartmentsResponse(HouseEntranceResponse):
    apartments: list[ApartmentResponse] = []


class HouseStructureResponse(HouseResponse):
    entrances: list[HouseEntranceWithApartmentsResponse] = []


class EntranceBulkGenerateSpec(BaseModel):
    number: int = Field(..., ge=1)
    floors_count: int = Field(..., ge=1)
    apartments_per_floor: int = Field(..., ge=1)
    start_number: int | None = Field(default=None, ge=1)
    start_floor: int = Field(default=1, ge=1)
    rooms_count: int | None = Field(default=None, ge=1)
    is_active: bool = True


class HouseWithStructureCreateRequest(HouseBase):
    entrances: list[EntranceBulkGenerateSpec]
