from pydantic import BaseModel

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
    # Здесь нет списков users или tickets

    class Config:
        from_attributes = True
