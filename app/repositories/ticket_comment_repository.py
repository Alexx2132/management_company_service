from sqlalchemy.orm import Session

from app.models.ticket_comment import TicketComment
from app.repositories.base import BaseRepository


class TicketCommentRepository(BaseRepository[TicketComment]):
    def __init__(self, db: Session):
        super().__init__(TicketComment, db)

    def list_for_ticket(self, ticket_id: int):
        return (
            self.db.query(TicketComment)
            .filter(TicketComment.ticket_id == ticket_id)
            .order_by(TicketComment.created_at.asc())
            .all()
        )