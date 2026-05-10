from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone


MOSCOW_TZ = timezone(timedelta(hours=3), name="MSK")


@dataclass(frozen=True)
class ExecutorAvailabilityState:
    target_date: date
    has_schedule: bool
    has_day_off: bool
    within_working_hours: bool
    is_working: bool


def moscow_now() -> datetime:
    return datetime.now(MOSCOW_TZ)


def moscow_today() -> date:
    return moscow_now().date()


def _is_time_in_range(start: time | None, end: time | None, current: time) -> bool:
    if start is None or end is None:
        return False

    if start <= end:
        return start <= current < end

    # Night shifts are rare here, but this keeps the check correct if one is configured.
    return current >= start or current < end


def get_executor_availability_state(profile, target_date: date | None = None, now: datetime | None = None) -> ExecutorAvailabilityState:
    current_moscow = now or moscow_now()
    date_to_check = target_date or current_moscow.date()
    weekday = date_to_check.weekday()

    schedules = [
        item
        for item in (getattr(profile, "work_schedules", None) or [])
        if item.is_active and item.weekday == weekday
    ]
    has_schedule = bool(schedules)

    has_day_off = any(
        item.is_active and item.off_date == date_to_check
        for item in (getattr(profile, "days_off", None) or [])
    )

    if date_to_check == current_moscow.date():
        current_time = current_moscow.time().replace(tzinfo=None)
        within_working_hours = any(
            _is_time_in_range(item.work_start, item.work_end, current_time)
            for item in schedules
        )
    else:
        within_working_hours = has_schedule

    return ExecutorAvailabilityState(
        target_date=date_to_check,
        has_schedule=has_schedule,
        has_day_off=has_day_off,
        within_working_hours=within_working_hours,
        is_working=has_schedule and within_working_hours and not has_day_off,
    )
