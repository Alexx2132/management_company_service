from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from app.models.remark import Remark, RemarkStatus


class RemarkRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, remark_id: int) -> Optional[Remark]:
        return (
            self.db.query(Remark)
            .options(joinedload(Remark.issuer), joinedload(Remark.executor), joinedload(Remark.canceled_by))
            .filter(Remark.id == remark_id)
            .first()
        )

    def list_sent(self, issuer_id: int, skip: int = 0, limit: int = 100, status: RemarkStatus | None = None) -> List[Remark]:
        q = (
            self.db.query(Remark)
            .options(joinedload(Remark.issuer), joinedload(Remark.executor), joinedload(Remark.canceled_by))
            .filter(Remark.issuer_id == issuer_id)
            .order_by(Remark.created_at.desc())
        )
        if status:
            q = q.filter(Remark.status == status)
        return q.offset(skip).limit(limit).all()

    def list_my(self, executor_id: int, skip: int = 0, limit: int = 100, status: RemarkStatus | None = None) -> List[Remark]:
        q = (
            self.db.query(Remark)
            .options(joinedload(Remark.issuer), joinedload(Remark.executor), joinedload(Remark.canceled_by))
            .filter(Remark.executor_id == executor_id)
            .order_by(Remark.created_at.desc())
        )
        if status:
            q = q.filter(Remark.status == status)
        return q.offset(skip).limit(limit).all()

    # ✅ NEW: auditor sees ALL
    def list_all(
        self,
        skip: int = 0,
        limit: int = 100,
        status: RemarkStatus | None = None,
        issuer_id: int | None = None,
        executor_id: int | None = None
    ) -> List[Remark]:
        q = (
            self.db.query(Remark)
            .options(joinedload(Remark.issuer), joinedload(Remark.executor), joinedload(Remark.canceled_by))
            .order_by(Remark.created_at.desc())
        )

        if status:
            q = q.filter(Remark.status == status)
        if issuer_id:
            q = q.filter(Remark.issuer_id == issuer_id)
        if executor_id:
            q = q.filter(Remark.executor_id == executor_id)

        return q.offset(skip).limit(limit).all()

    def create(self, obj: Remark) -> Remark:
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def save(self, obj: Remark) -> Remark:
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj