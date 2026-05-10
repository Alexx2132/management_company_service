from datetime import datetime, timedelta
from typing import List

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.ticket import Ticket, TicketStatus
from app.repositories.base import BaseRepository


class TicketRepository(BaseRepository[Ticket]):
    def __init__(self, db: Session):
        super().__init__(Ticket, db)

    def get_by_author(self, author_id: int) -> List[Ticket]:
        return self.db.query(Ticket).filter(Ticket.author_id == author_id).all()

    def get_filtered(
            self,
            status: TicketStatus | None = None,
            house_id: int | None = None,
            executor_id: int | None = None,
            limit: int = 100,
            skip: int = 0,
            created_from: datetime | None = None,
            created_to: datetime | None = None,
            overdue_hours: int | None = None
    ) -> List[Ticket]:
        query = self.db.query(Ticket)

        if status:
            query = query.filter(Ticket.status == status)

        if house_id:
            query = query.filter(Ticket.house_id == house_id)

        if executor_id:
            query = query.filter(Ticket.executor_id == executor_id)

        if created_from:
            query = query.filter(Ticket.created_at >= created_from)

        if created_to:
            query = query.filter(Ticket.created_at <= created_to)

        if overdue_hours is not None:
            try:
                oh = int(overdue_hours)
            except Exception:
                oh = None

            if oh is not None and oh > 0:
                threshold = datetime.utcnow() - timedelta(hours=oh)
                query = query.filter(Ticket.created_at <= threshold)
                query = query.filter(Ticket.status.notin_([
                    TicketStatus.DONE,
                    TicketStatus.CLOSED,
                    TicketStatus.CANCELED
                ]))

        return query.order_by(Ticket.created_at.desc()).offset(skip).limit(limit).all()

    def get_for_resident(self, house_id: int, apartment: str | None = None, apartment_id: int | None = None) -> List[Ticket]:
        if not house_id:
            return []

        query = self.db.query(Ticket).filter(Ticket.house_id == house_id)

        if apartment_id is not None:
            if apartment:
                query = query.filter(
                    or_(
                        Ticket.apartment_id == apartment_id,
                        and_(Ticket.apartment_id.is_(None), Ticket.apartment == apartment)
                    )
                )
            else:
                query = query.filter(Ticket.apartment_id == apartment_id)
        else:
            if not apartment:
                return []
            query = query.filter(Ticket.apartment == apartment)

        return query.order_by(Ticket.created_at.desc()).all()