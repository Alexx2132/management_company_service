from app.models.ticket_complaint import (  # <- ВАЖНО: здесь должен быть файл с реальными моделями
    TicketComplaint,
    ComplaintFile,
    ComplaintType,
    ComplaintStatus,
)

__all__ = [
    "TicketComplaint",
    "ComplaintFile",
    "ComplaintType",
    "ComplaintStatus",
]