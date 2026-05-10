from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.remark import RemarkStatus
from app.schemas.remark import RemarkCreate, RemarkResponse
from app.services.remark_service import RemarkService

router = APIRouter()


@router.post("/", response_model=RemarkResponse)
def create_remark(
    data: RemarkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = RemarkService(db)
    return service.create_remark(data, current_user)


@router.get("/sent", response_model=list[RemarkResponse])
def list_sent(
    skip: int = 0,
    limit: int = 100,
    status: RemarkStatus | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = RemarkService(db)
    return service.list_sent(current_user, skip=skip, limit=limit, status=status)


@router.get("/my", response_model=list[RemarkResponse])
def list_my(
    skip: int = 0,
    limit: int = 100,
    status: RemarkStatus | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = RemarkService(db)
    return service.list_my(current_user, skip=skip, limit=limit, status=status)


# ✅ NEW: auditor/admin sees all remarks
@router.get("/all", response_model=list[RemarkResponse])
def list_all(
    skip: int = 0,
    limit: int = 200,
    status: RemarkStatus | None = None,
    issuer_id: int | None = None,
    executor_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = RemarkService(db)
    return service.list_all(
        current_user=current_user,
        skip=skip,
        limit=limit,
        status=status,
        issuer_id=issuer_id,
        executor_id=executor_id
    )


@router.get("/{remark_id}", response_model=RemarkResponse)
def get_remark(
    remark_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = RemarkService(db)
    return service.get_remark(remark_id, current_user)


@router.post("/{remark_id}/cancel", response_model=RemarkResponse)
def cancel_remark(
    remark_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = RemarkService(db)
    return service.cancel_remark(remark_id, current_user)