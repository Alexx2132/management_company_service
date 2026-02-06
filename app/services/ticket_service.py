from typing import List
from sqlalchemy.orm import Session

from app.repositories.ticket_repository import TicketRepository
from app.schemas.ticket import TicketCreate, TicketUpdate
from app.models.user import User, UserRole
from app.models.ticket import Ticket
from app.models.ticket import TicketStatus
from app.schemas.ticket import TicketAssign
import shutil
import uuid
import os
from fastapi import UploadFile, HTTPException
from app.models.ticket import TicketFile
class TicketService:
    def __init__(self, db: Session):
        self.ticket_repo = TicketRepository(db)

    def upload_file(self, ticket_id: int, file: UploadFile, user: User) -> TicketFile:
        # 1. Ищем заявку
        ticket = self.ticket_repo.get_by_id(ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        # 2. Проверка прав (автор, админ или диспетчер)
        # Исполнитель тоже может грузить фото (отчет)
        if user.role == "resident" and ticket.author_id != user.id:
            raise HTTPException(status_code=403, detail="Not your ticket")

        # 3. Проверка лимита (FR: не более 5 фото)
        # Обращаемся к ticket.files (SQLAlchemy сама подгрузит их)
        if len(ticket.files) >= 10:
            raise HTTPException(status_code=400, detail="Max 10 photos allowed")

        # 4. Генерируем уникальное имя файла
        # file.filename может быть "photo.jpg". Делаем "uuid-photo.jpg"
        file_ext = file.filename.split(".")[-1]
        unique_name = f"{uuid.uuid4()}.{file_ext}"
        save_path = f"static/uploads/{unique_name}"

        # 5. Сохраняем физически на диск
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 6. Сохраняем запись в БД
        # Путь для API должен начинаться со слэша
        db_file = TicketFile(
            ticket_id=ticket_id,
            file_path=f"/{save_path}"
        )
        self.ticket_repo.db.add(db_file)
        self.ticket_repo.db.commit()
        self.ticket_repo.db.refresh(db_file)

        return db_file

    def delete_file(self, file_id: int, user: User):
        # 1. Ищем файл в БД
        # Нам нужно найти файл, но репозитория файлов у нас нет.
        # Можно сделать запрос напрямую через db (Session).
        # Не забудьте импорт: from app.models.ticket import TicketFile

        file_obj = self.ticket_repo.db.query(TicketFile).filter(TicketFile.id == file_id).first()

        if not file_obj:
            raise HTTPException(status_code=404, detail="File not found")

        ticket = file_obj.ticket  # Получаем связанную заявку

        # 2. Проверка прав
        # Удалять может: Админ, Диспетчер, или Автор заявки (если она еще не закрыта)
        is_admin = user.role in [UserRole.ADMIN, UserRole.DISPATCHER]
        is_author = (ticket.author_id == user.id)

        if not (is_admin or is_author):
            raise HTTPException(status_code=403, detail="Not enough permissions")

        # 3. Удаляем файл с диска
        file_system_path = file_obj.file_path.lstrip("/")

        if os.path.exists(file_system_path):
            os.remove(file_system_path)

        # 4. Удаляем из БД
        self.ticket_repo.db.delete(file_obj)
        self.ticket_repo.db.commit()

        return {"status": "deleted"}

    def create_ticket(self, ticket_in: TicketCreate, user: User) -> Ticket:
        # 1. Превращаем Pydantic модель в словарь
        data = ticket_in.model_dump()

        # 2. Извлекаем (вырезаем) поле created_for_user_id
        # Мы удаляем его из data, потому что в таблице Tickets такого столбца нет!
        target_user_id = data.pop("created_for_user_id", None)

        # 3. Логика подмены автора
        # Если текущий пользователь - Админ или Диспетчер...
        if user.role in [UserRole.ADMIN, UserRole.DISPATCHER] and target_user_id:
            # ... и он указал ID другого человека -> ставим этого человека автором
            data["author_id"] = target_user_id
        else:
            # Во всех остальных случаях (жилец или диспетчер не указал ID)
            # автором становится тот, кто делает запрос
            data["author_id"] = user.id

        # 4. Создаем запись в БД
        return self.ticket_repo.create(data)

    def get_tickets(
            self,
            user: User,
            status: TicketStatus | None = None,
            house_id: int | None = None,
            executor_id: int | None = None
    ) -> List[Ticket]:

        # 1. Персонал
        if user.role in [UserRole.ADMIN, UserRole.DISPATCHER, UserRole.AUDITOR]:
            return self.ticket_repo.get_filtered(
                status=status,
                house_id=house_id,
                executor_id=executor_id
            )

    def assign_ticket(self, ticket_id: int, assign_data: TicketAssign, user: User) -> Ticket:
        # 1. Проверка прав (Только Админ или Диспетчер)
        if user.role not in [UserRole.ADMIN, UserRole.DISPATCHER]:
            raise HTTPException(status_code=403, detail="Not enough permissions")

        # 2. Поиск заявки
        ticket = self.ticket_repo.get_by_id(ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        # 3. Обновление полей
        # В идеале нужно проверить, существует ли такой executor_id в базе юзеров,
        # но пока доверимся диспетчеру.
        ticket.executor_id = assign_data.executor_id
        ticket.status = TicketStatus.ASSIGNED

        # 4. Сохранение (через commit, так как мы меняли объект ORM напрямую)
        self.ticket_repo.db.commit()
        self.ticket_repo.db.refresh(ticket)
        return ticket

    def cancel_ticket(self, ticket_id: int, user: User):
        ticket = self.ticket_repo.get_by_id(ticket_id)
        if not ticket:
            raise HTTPException(404, "Not found")

        # Логика для Жильца
        if user.role == "resident":
            if ticket.author_id != user.id:
                raise HTTPException(403, "Not your ticket")
            if ticket.status != TicketStatus.CREATED:
                raise HTTPException(400, "Cannot cancel ticket in progress")

        # Логика для Админа/Диспетчера (они могут всё)
        # Исполнитель не может отменять (только отклонять, это другой кейс)

        ticket.status = TicketStatus.CANCELED
        self.ticket_repo.db.commit()
        return {"status": "canceled"}

    def get_tickets(
            self,
            user: User,
            status: TicketStatus | None = None,
            house_id: int | None = None,
            executor_id: int | None = None
    ) -> List[Ticket]:

        # 1. Персонал (Админ, Диспетчер, Аудитор) видит всё + фильтры
        if user.role in [UserRole.ADMIN, UserRole.DISPATCHER, UserRole.AUDITOR]:
            return self.ticket_repo.get_filtered(
                status=status,
                house_id=house_id,
                executor_id=executor_id
            )

        # 2. Исполнитель видит только свои (фильтр по executor_id принудительный)
        elif user.role == UserRole.EXECUTOR:
            # Исполнитель может фильтровать свои задачи по статусу
            return self.ticket_repo.get_filtered(
                executor_id=user.id,
                status=status
            )

        # 3. Жилец видит только свои
        else:
            return self.ticket_repo.get_by_author(user.id)


def update_status(self, ticket_id: int, update_data: TicketUpdate, user: User) -> Ticket:
    ticket = self.ticket_repo.get_by_id(ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")

    new_status = update_data.status
    comment = update_data.comment

    # --- ЛОГИКА ДЛЯ ИСПОЛНИТЕЛЯ (Master) ---
    if user.role == UserRole.EXECUTOR:
        # Мастер может менять только свои заявки
        if ticket.executor_id != user.id:
            raise HTTPException(403, "Not your ticket")

        # FR-11: Отказ от заявки (Делегирование)
        # Мастер возвращает заявку Диспетчеру (статус CREATED или спец статус)
        if new_status == TicketStatus.CREATED:
            if not comment:
                raise HTTPException(400, "Comment required for rejection")
            # Сбрасываем исполнителя
            ticket.executor_id = None
            ticket.result_comment = f"Отказ от {user.full_name}: {comment}"

        # FR-16: Завершение работы
        elif new_status == TicketStatus.DONE:
            # Проверка фото (обязательно)
            if len(ticket.files) == 0:
                raise HTTPException(400, "Photo report required")
            ticket.result_comment = comment

        # Взятие в работу
        elif new_status == TicketStatus.IN_PROGRESS:
            pass  # Просто меняем статус

        else:
            raise HTTPException(400, "Invalid status transition for Executor")

    # --- ЛОГИКА ДЛЯ ЖИЛЬЦА (Resident) ---
    elif user.role == UserRole.RESIDENT:
        # Жилец может закрыть заявку (подтвердить выполнение)
        if ticket.author_id != user.id:
            raise HTTPException(403, "Not your ticket")

        if new_status == TicketStatus.CLOSED:  # (Предполагаем, что есть такой статус)
            pass
        else:
            raise HTTPException(400, "Residents can only close tickets")

    # --- ЛОГИКА ДЛЯ ДИСПЕТЧЕРА ---
    elif user.role in [UserRole.ADMIN, UserRole.DISPATCHER]:
        # Могут всё
        pass

    # Применяем изменения
    ticket.status = new_status
    self.ticket_repo.db.commit()
    self.ticket_repo.db.refresh(ticket)
    return ticket