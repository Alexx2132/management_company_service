from pydantic import BaseModel


class CategoryBase(BaseModel):
    name: str
    category_type: str = "problem"


class CategoryCreate(CategoryBase):
    pass


class CategoryResponse(CategoryBase):
    id: int

    class Config:
        from_attributes = True
