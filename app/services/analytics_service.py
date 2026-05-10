from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.ticket import Ticket
from app.schemas.analytics import (
    AnalyticsCategoryBucket,
    AnalyticsStatusBucket,
    TicketAnalyticsOverviewResponse,
)


class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db

    def get_ticket_overview(
        self,
        house_id: int | None = None,
        category_id: int | None = None,
        place_category_id: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None
    ) -> TicketAnalyticsOverviewResponse:
        base_query = self.db.query(Ticket)

        if house_id is not None:
            base_query = base_query.filter(Ticket.house_id == house_id)
        if category_id is not None:
            base_query = base_query.filter(Ticket.category_id == category_id)
        if place_category_id is not None:
            base_query = base_query.filter(Ticket.place_category_id == place_category_id)

        if date_from is not None:
            base_query = base_query.filter(Ticket.created_at >= date_from)

        if date_to is not None:
            base_query = base_query.filter(Ticket.created_at <= date_to)

        total_tickets = base_query.count()

        status_rows = (
            base_query.with_entities(Ticket.status, func.count(Ticket.id))
            .group_by(Ticket.status)
            .all()
        )

        status_buckets = [
            AnalyticsStatusBucket(
                status=(row[0].value if hasattr(row[0], "value") else str(row[0])),
                count=row[1]
            )
            for row in status_rows
        ]

        category_buckets = self._build_category_buckets(
            foreign_key=Ticket.category_id,
            category_type="problem",
            empty_label="Без категории",
            house_id=house_id,
            category_id=category_id,
            place_category_id=place_category_id,
            date_from=date_from,
            date_to=date_to,
        )

        location_buckets = self._build_category_buckets(
            foreign_key=Ticket.place_category_id,
            category_type="location",
            empty_label="Место не указано",
            house_id=house_id,
            category_id=category_id,
            place_category_id=place_category_id,
            date_from=date_from,
            date_to=date_to,
        )

        category_buckets.sort(key=lambda x: x.count, reverse=True)
        location_buckets.sort(key=lambda x: x.count, reverse=True)
        status_buckets.sort(key=lambda x: x.count, reverse=True)

        return TicketAnalyticsOverviewResponse(
            total_tickets=total_tickets,
            status_buckets=status_buckets,
            category_buckets=category_buckets,
            location_buckets=location_buckets,
        )

    def _apply_ticket_filters(
        self,
        query,
        house_id: int | None = None,
        category_id: int | None = None,
        place_category_id: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ):
        if house_id is not None:
            query = query.filter(Ticket.house_id == house_id)
        if category_id is not None:
            query = query.filter(Ticket.category_id == category_id)
        if place_category_id is not None:
            query = query.filter(Ticket.place_category_id == place_category_id)
        if date_from is not None:
            query = query.filter(Ticket.created_at >= date_from)
        if date_to is not None:
            query = query.filter(Ticket.created_at <= date_to)
        return query

    def _build_category_buckets(
        self,
        foreign_key,
        category_type: str,
        empty_label: str,
        house_id: int | None = None,
        category_id: int | None = None,
        place_category_id: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[AnalyticsCategoryBucket]:
        query = (
            self.db.query(Category.id, Category.name, func.count(Ticket.id))
            .filter(Category.category_type == category_type)
            .outerjoin(Ticket, foreign_key == Category.id)
        )
        query = self._apply_ticket_filters(
            query,
            house_id=house_id,
            category_id=category_id,
            place_category_id=place_category_id,
            date_from=date_from,
            date_to=date_to,
        )

        buckets = [
            AnalyticsCategoryBucket(category_id=row[0], category_name=row[1], count=row[2])
            for row in query.group_by(Category.id, Category.name).all()
        ]

        empty_query = self.db.query(func.count(Ticket.id)).filter(foreign_key.is_(None))
        empty_query = self._apply_ticket_filters(
            empty_query,
            house_id=house_id,
            category_id=category_id,
            place_category_id=place_category_id,
            date_from=date_from,
            date_to=date_to,
        )
        empty_count = empty_query.scalar() or 0
        if empty_count > 0:
            buckets.append(AnalyticsCategoryBucket(category_id=None, category_name=empty_label, count=empty_count))
        return buckets
