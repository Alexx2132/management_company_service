from pydantic import BaseModel, Field


class AnalyticsStatusBucket(BaseModel):
    status: str
    count: int


class AnalyticsCategoryBucket(BaseModel):
    category_id: int | None = None
    category_name: str
    count: int


class TicketAnalyticsOverviewResponse(BaseModel):
    total_tickets: int
    status_buckets: list[AnalyticsStatusBucket]
    category_buckets: list[AnalyticsCategoryBucket]
    location_buckets: list[AnalyticsCategoryBucket] = Field(default_factory=list)
