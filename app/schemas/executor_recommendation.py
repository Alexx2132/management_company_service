from pydantic import BaseModel


class ExecutorRecommendationResponse(BaseModel):
    executor_id: int
    user_id: int
    full_name: str
    contact_phone: str | None = None
    house_id: int | None = None
    primary_specialty: str | None = None

    working_today: bool
    has_day_off_today: bool
    can_assign: bool

    assigned_count: int
    in_progress_count: int
    active_total_count: int

    score: int
    reasons: list[str]