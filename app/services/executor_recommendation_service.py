from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.models.executor import ExecutorProfile, ExecutorSpecialty
from app.models.ticket import Ticket, TicketStatus
from app.schemas.executor_recommendation import ExecutorRecommendationResponse
from app.services.executor_availability import get_executor_availability_state, moscow_today


FINAL_STATUSES = [TicketStatus.DONE, TicketStatus.CLOSED, TicketStatus.CANCELED]


class ExecutorRecommendationService:
    def __init__(self, db: Session):
        self.db = db

    def _normalize(self, value: str | None) -> str:
        return (value or "").strip().lower()

    def _resolve_contact_phone(self, profile: ExecutorProfile) -> str | None:
        login_like_values = {
            self._normalize(getattr(profile.user, "login", None)),
        }
        login_like_values.discard("")

        direct_contact = (getattr(profile.user, "contact_phone", None) or "").strip()
        if direct_contact and direct_contact.lower() not in login_like_values:
            return direct_contact

        legacy_profile_phone = (getattr(profile, "phone", None) or "").strip()
        if legacy_profile_phone and legacy_profile_phone.lower() not in login_like_values:
            return legacy_profile_phone

        return None

    def _specialty_match(self, profile: ExecutorProfile, ticket: Ticket) -> bool:
        category_name = ""
        title = self._normalize(getattr(ticket, "title", None))
        description = self._normalize(getattr(ticket, "description", None))

        if getattr(ticket, "category", None) is not None:
            category_name = self._normalize(getattr(ticket.category, "name", None))

        target = f"{category_name} {title} {description}".strip()

        if not target:
            return False

        for item in profile.specialties:
            if item.specialty is None:
                continue

            spec_name = self._normalize(getattr(item.specialty, "name", None))
            spec_code = self._normalize(getattr(item.specialty, "code", None))

            if spec_name and (spec_name in target or target in spec_name):
                return True

            if spec_code and spec_code in target:
                return True

        return False

    def _primary_specialty_name(self, profile: ExecutorProfile) -> str | None:
        for item in profile.specialties:
            if item.is_primary and item.specialty is not None:
                return item.specialty.name

        if profile.specialties and profile.specialties[0].specialty is not None:
            return profile.specialties[0].specialty.name

        return None

    def recommend_for_ticket(self, ticket_id: int, top: int = 10) -> list[ExecutorRecommendationResponse]:
        ticket = (
            self.db.query(Ticket)
            .options(joinedload(Ticket.category))
            .filter(Ticket.id == ticket_id)
            .first()
        )
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        profiles = (
            self.db.query(ExecutorProfile)
            .options(
                joinedload(ExecutorProfile.user),
                joinedload(ExecutorProfile.specialties).joinedload(ExecutorSpecialty.specialty),
                joinedload(ExecutorProfile.work_schedules),
                joinedload(ExecutorProfile.days_off),
            )
            .filter(ExecutorProfile.is_active.is_(True))
            .all()
        )

        today = moscow_today()

        result: list[ExecutorRecommendationResponse] = []

        for profile in profiles:
            if profile.user is None:
                continue

            reasons: list[str] = []
            score = 0

            same_house = ticket.house_id is not None and profile.house_id == ticket.house_id
            no_house_binding = profile.house_id is None

            if same_house:
                score += 40
                reasons.append("тот же дом")
            elif no_house_binding:
                score += 10
                reasons.append("без жёсткой привязки к дому")
            else:
                score -= 10
                reasons.append("привязан к другому дому")

            specialty_match = self._specialty_match(profile, ticket)
            if specialty_match:
                score += 50
                reasons.append("подходит по специальности")
            elif not profile.specialties:
                score -= 20
                reasons.append("специальности не заданы")
            else:
                score -= 5
                reasons.append("точное совпадение специальности не найдено")

            availability = get_executor_availability_state(profile, target_date=today)
            working_today = availability.is_working
            has_day_off_today = availability.has_day_off

            if has_day_off_today:
                score -= 100
                reasons.append("сегодня выходной")
            elif working_today:
                score += 20
                reasons.append("сейчас в рабочем графике")
            elif availability.has_schedule:
                score -= 15
                reasons.append("сейчас вне рабочего времени")
            else:
                score -= 15
                reasons.append("сегодня вне графика")

            assigned_count = self.db.query(Ticket).filter(
                Ticket.executor_id == profile.user_id,
                Ticket.status == TicketStatus.ASSIGNED
            ).count()

            in_progress_count = self.db.query(Ticket).filter(
                Ticket.executor_id == profile.user_id,
                Ticket.status == TicketStatus.IN_PROGRESS
            ).count()

            active_total_count = self.db.query(Ticket).filter(
                Ticket.executor_id == profile.user_id,
                Ticket.status.notin_(FINAL_STATUSES)
            ).count()

            score -= assigned_count * 5
            score -= in_progress_count * 8
            score -= active_total_count * 3

            if active_total_count == 0:
                reasons.append("сейчас свободен")
            elif active_total_count <= 2:
                reasons.append("небольшая загрузка")
            else:
                reasons.append("есть текущая загрузка")

            result.append(
                ExecutorRecommendationResponse(
                    executor_id=profile.id,
                    user_id=profile.user_id,
                    full_name=f"{profile.last_name} {profile.first_name}".strip(),
                    contact_phone=self._resolve_contact_phone(profile),
                    house_id=profile.house_id,
                    primary_specialty=self._primary_specialty_name(profile),
                    working_today=working_today,
                    has_day_off_today=has_day_off_today,
                    can_assign=(working_today and not has_day_off_today),
                    assigned_count=assigned_count,
                    in_progress_count=in_progress_count,
                    active_total_count=active_total_count,
                    score=score,
                    reasons=reasons,
                )
            )

        result.sort(key=lambda x: x.score, reverse=True)
        return result[:top]
