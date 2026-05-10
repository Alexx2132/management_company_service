from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.profanity import ensure_clean_text
from app.models.ticket import TicketStatus
from app.models.ticket_comment import TicketComment
from app.models.user import User, UserRole
from app.repositories.ticket_comment_repository import TicketCommentRepository
from app.services.notification_service import NotificationService
from app.services.ticket_service import TicketService


class TicketCommentService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = TicketCommentRepository(db)
        self.ticket_service = TicketService(db)
        self.notifications = NotificationService(db)

    def _get_ticket_for_user(self, ticket_id: int, user: User, for_write: bool = False):
        ticket = self.ticket_service.get_ticket_by_id(ticket_id, user)

        if user.role == UserRole.RESIDENT and ticket.author_id != user.id:
            raise HTTPException(status_code=403, detail="Only ticket author can access comments")

        if user.role == UserRole.EXECUTOR and ticket.executor_id != user.id:
            raise HTTPException(status_code=403, detail="Only assigned executor can access comments")

        if for_write and ticket.status == TicketStatus.CANCELED:
            raise HTTPException(status_code=400, detail="Cannot comment canceled ticket")

        return ticket

    def list_comments(self, ticket_id: int, current_user: User):
        self._get_ticket_for_user(ticket_id, current_user, for_write=False)
        comments = self.repo.list_for_ticket(ticket_id)

        if current_user.role in [UserRole.ADMIN, UserRole.DISPATCHER, UserRole.AUDITOR]:
            return comments

        return [comment for comment in comments if not comment.is_internal]

    def create_comment(self, ticket_id: int, message: str, is_internal: bool, current_user: User) -> TicketComment:
        ticket = self._get_ticket_for_user(ticket_id, current_user, for_write=True)

        if not message or not message.strip():
            raise HTTPException(status_code=400, detail="message is required")

        ensure_clean_text(message)

        if current_user.role == UserRole.RESIDENT:
            self.ticket_service._ensure_resident_not_banned(current_user)

        if is_internal and current_user.role not in [UserRole.ADMIN, UserRole.DISPATCHER, UserRole.AUDITOR]:
            raise HTTPException(status_code=403, detail="Only staff can create internal comments")

        obj = TicketComment(
            ticket_id=ticket.id,
            author_id=current_user.id,
            message=message.strip(),
            is_internal=is_internal,
        )
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)

        self._notify_about_comment(ticket, obj, current_user)
        return obj

    def _notify_about_comment(self, ticket, comment: TicketComment, author: User) -> None:
        if comment.is_internal:
            from app.models.user import User

            staff_users = (
                self.db.query(User)
                .filter(User.role.in_([UserRole.ADMIN, UserRole.DISPATCHER, UserRole.AUDITOR]))
                .all()
            )
            recipient_ids = {staff_user.id for staff_user in staff_users if staff_user.id != author.id}
            if not recipient_ids:
                return
            self.notifications.notify_many(
                user_ids=recipient_ids,
                title=f"Внутренний комментарий по заявке #{ticket.id}",
                message=comment.message,
                notif_type="ticket_comment_internal",
                ticket_id=ticket.id,
            )
            return

        recipient_ids: set[int] = set()

        if ticket.author_id != author.id:
            recipient_ids.add(ticket.author_id)

        if ticket.executor_id and ticket.executor_id != author.id:
            recipient_ids.add(ticket.executor_id)

        if author.role == UserRole.RESIDENT:
            from app.models.user import User

            staff_users = (
                self.db.query(User)
                .filter(User.role.in_([UserRole.ADMIN, UserRole.DISPATCHER, UserRole.AUDITOR]))
                .all()
            )
            for staff_user in staff_users:
                if staff_user.id != author.id:
                    recipient_ids.add(staff_user.id)

        if not recipient_ids:
            return

        self.notifications.notify_many(
            user_ids=recipient_ids,
            title=f"Новый комментарий по заявке #{ticket.id}",
            message=comment.message,
            notif_type="ticket_comment",
            ticket_id=ticket.id,
        )
