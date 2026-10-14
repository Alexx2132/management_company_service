from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_file_user
from app.db.operations import run_db
from app.models.ticket import TicketFile, TicketFileKind
from app.models.ticket_complaint import ComplaintFile
from app.models.user import User, UserRole
from app.services.ticket_service import TicketService
from app.services.ticket_complaint_service import TicketComplaintService

router = APIRouter()
MEDIA_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
PRIVATE_HEADERS = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox"}


def image_response(file_path: str) -> FileResponse:
    root = Path("static/uploads").resolve()
    path = Path(file_path.lstrip("/")).resolve()
    if not path.is_relative_to(root) or path.suffix.lower() not in MEDIA_TYPES or not path.is_file():
        raise HTTPException(status_code=404, detail="Изображение не найдено")
    return FileResponse(path, media_type=MEDIA_TYPES[path.suffix.lower()], headers=PRIVATE_HEADERS)


@router.get("/static/uploads/tickets/{ticket_id}/{filename}", include_in_schema=False)
async def ticket_image(ticket_id: int, filename: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_file_user)):
    def operation(session):
        service = TicketService(session)
        ticket = service.get_ticket(ticket_id, user)
        file_path = f"/static/uploads/tickets/{ticket_id}/{filename}"
        file = session.query(TicketFile).filter(TicketFile.ticket_id == ticket_id, TicketFile.file_path == file_path).first()
        if not file:
            raise HTTPException(status_code=404, detail="Изображение не найдено")
        if user.role == UserRole.EXECUTOR and ticket.executor_id != user.id and file.kind == TicketFileKind.AFTER:
            raise HTTPException(status_code=403, detail="Нет доступа к фотоотчёту другого исполнителя")
        return image_response(file_path)
    return await run_db(db, operation)


@router.get("/static/uploads/complaints/{complaint_id}/{filename}", include_in_schema=False)
async def complaint_image(complaint_id: int, filename: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_file_user)):
    def operation(session):
        TicketComplaintService(session)._get_accessible_complaint(complaint_id, user)
        file_path = f"/static/uploads/complaints/{complaint_id}/{filename}"
        file = session.query(ComplaintFile.id).filter(ComplaintFile.complaint_id == complaint_id, ComplaintFile.file_path == file_path).first()
        if not file:
            raise HTTPException(status_code=404, detail="Изображение не найдено")
        return image_response(file_path)
    return await run_db(db, operation)


class PublicBackgrounds(StaticFiles):
    async def get_response(self, path, scope):
        if Path(path).suffix.lower() not in MEDIA_TYPES:
            raise HTTPException(status_code=404, detail="Изображение не найдено")
        response = await super().get_response(path, scope)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "sandbox"
        return response
