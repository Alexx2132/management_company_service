from typing import List  # List все равно нужен для аннотации возвращаемого значения
from sqlalchemy.orm import Session
from app.repositories.base import BaseRepository
from app.models.ticket import Ticket, TicketStatus


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
            skip: int = 0
    ) -> List[Ticket]:
        query = self.db.query(Ticket)

        if status:
            query = query.filter(Ticket.status == status)

        if house_id:
            query = query.filter(Ticket.house_id == house_id)

        if executor_id:
            query = query.filter(Ticket.executor_id == executor_id)

        return query.order_by(Ticket.created_at.desc()).offset(skip).limit(limit).all()

