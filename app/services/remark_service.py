from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.profanity import ensure_clean_text
from app.models.user import User, UserRole
from app.models.remark import Remark, RemarkStatus
from app.repositories.remark_repository import RemarkRepository
from app.schemas.remark import RemarkCreate
from app.services.permissions import can_manage_remarks


class RemarkService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = RemarkRepository(db)

    def _ensure_staff_can_issue(self, user: User):
        if user.role not in [UserRole.DISPATCHER, UserRole.AUDITOR] and not can_manage_remarks(user):
            raise HTTPException(status_code=403, detail="Only dispatcher or auditor can issue remarks")

    def _ensure_recipient_can_view(self, user: User):
        if user.role not in [UserRole.EXECUTOR, UserRole.DISPATCHER]:
            raise HTTPException(status_code=403, detail="Only executor or dispatcher can view own remarks")

    def _ensure_auditor_or_admin(self, user: User):
        if user.role not in [UserRole.AUDITOR, UserRole.ADMIN] and not can_manage_remarks(user):
            raise HTTPException(status_code=403, detail="Only auditor or admin can view all remarks")

    def create_remark(self, data: RemarkCreate, current_user: User) -> Remark:
        self._ensure_staff_can_issue(current_user)
        ensure_clean_text(data.comment)

        from app.repositories.user_repository import UserRepository
        urepo = UserRepository(self.db)
        executor = urepo.get_by_id(data.executor_id)
        if not executor:
            raise HTTPException(status_code=404, detail="Recipient not found")

        allowed_roles = {UserRole.EXECUTOR}
        if current_user.role == UserRole.AUDITOR:
            allowed_roles.add(UserRole.DISPATCHER)

        if executor.role not in allowed_roles:
            raise HTTPException(status_code=400, detail="Selected user cannot receive this remark")

        obj = Remark(
            issuer_id=current_user.id,
            executor_id=data.executor_id,
            comment=data.comment.strip(),
            status=RemarkStatus.ACTIVE,
            created_at=datetime.utcnow()
        )
        return self.repo.create(obj)

    def list_sent(self, current_user: User, skip: int = 0, limit: int = 100, status: RemarkStatus | None = None):
        self._ensure_staff_can_issue(current_user)
        return self.repo.list_sent(current_user.id, skip=skip, limit=limit, status=status)

    def list_my(self, current_user: User, skip: int = 0, limit: int = 100, status: RemarkStatus | None = None):
        self._ensure_recipient_can_view(current_user)
        return self.repo.list_my(current_user.id, skip=skip, limit=limit, status=status)

    # ✅ NEW
    def list_all(
        self,
        current_user: User,
        skip: int = 0,
        limit: int = 100,
        status: RemarkStatus | None = None,
        issuer_id: int | None = None,
        executor_id: int | None = None
    ):
        self._ensure_auditor_or_admin(current_user)
        return self.repo.list_all(skip=skip, limit=limit, status=status, issuer_id=issuer_id, executor_id=executor_id)

    def get_remark(self, remark_id: int, current_user: User) -> Remark:
        obj = self.repo.get_by_id(remark_id)
        if not obj:
            raise HTTPException(status_code=404, detail="Remark not found")

        if current_user.id not in [obj.issuer_id, obj.executor_id] and current_user.role not in [UserRole.AUDITOR, UserRole.ADMIN] and not can_manage_remarks(current_user):
            raise HTTPException(status_code=403, detail="Not enough permissions")

        return obj

    def cancel_remark(self, remark_id: int, current_user: User) -> Remark:
        self._ensure_staff_can_issue(current_user)

        obj = self.repo.get_by_id(remark_id)
        if not obj:
            raise HTTPException(status_code=404, detail="Remark not found")

        if obj.issuer_id != current_user.id:
            raise HTTPException(status_code=403, detail="You can cancel only your own remarks")

        if obj.status == RemarkStatus.CANCELED:
            return obj

        obj.status = RemarkStatus.CANCELED
        obj.canceled_at = datetime.utcnow()
        obj.canceled_by_id = current_user.id

        return self.repo.save(obj)
