from datetime import date, datetime, time

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Time, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class ExecutorProfile(Base):
    __tablename__ = "executor_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    house_id = Column(Integer, ForeignKey("houses.id"), nullable=True, index=True)

    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    middle_name = Column(String, nullable=True)

    phone = Column(String, nullable=True)
    notes = Column(String, nullable=True)

    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="executor_profile")
    house = relationship("House")
    specialties = relationship(
        "ExecutorSpecialty",
        back_populates="executor",
        cascade="all, delete-orphan"
    )
    work_schedules = relationship(
        "ExecutorWorkSchedule",
        back_populates="executor",
        cascade="all, delete-orphan",
        order_by="ExecutorWorkSchedule.weekday"
    )
    days_off = relationship(
        "ExecutorDayOff",
        back_populates="executor",
        cascade="all, delete-orphan",
        order_by="ExecutorDayOff.off_date"
    )


class Specialty(Base):
    __tablename__ = "specialties"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=False, unique=True)

    executors = relationship(
        "ExecutorSpecialty",
        back_populates="specialty",
        cascade="all, delete-orphan"
    )

    @property
    def executor_count(self) -> int:
        return len(self.executors or [])

    @property
    def can_delete(self) -> bool:
        return self.executor_count == 0


class ExecutorSpecialty(Base):
    __tablename__ = "executor_specialties"
    __table_args__ = (
        UniqueConstraint("executor_id", "specialty_id", name="uq_executor_specialty"),
    )

    id = Column(Integer, primary_key=True, index=True)
    executor_id = Column(Integer, ForeignKey("executor_profiles.id"), nullable=False, index=True)
    specialty_id = Column(Integer, ForeignKey("specialties.id"), nullable=False, index=True)
    is_primary = Column(Boolean, nullable=False, default=False)

    executor = relationship("ExecutorProfile", back_populates="specialties")
    specialty = relationship("Specialty", back_populates="executors")


class ExecutorWorkSchedule(Base):
    __tablename__ = "executor_work_schedules"
    __table_args__ = (
        UniqueConstraint("executor_id", "weekday", name="uq_executor_work_schedule_weekday"),
    )

    id = Column(Integer, primary_key=True, index=True)
    executor_id = Column(Integer, ForeignKey("executor_profiles.id"), nullable=False, index=True)

    weekday = Column(Integer, nullable=False)  # 0 Monday ... 6 Sunday
    work_start = Column(Time, nullable=False, default=time(hour=9, minute=0))
    work_end = Column(Time, nullable=False, default=time(hour=18, minute=0))
    is_active = Column(Boolean, nullable=False, default=True)

    executor = relationship("ExecutorProfile", back_populates="work_schedules")


class ExecutorDayOff(Base):
    __tablename__ = "executor_days_off"
    __table_args__ = (
        UniqueConstraint("executor_id", "off_date", name="uq_executor_day_off_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    executor_id = Column(Integer, ForeignKey("executor_profiles.id"), nullable=False, index=True)

    off_date = Column(Date, nullable=False, default=date.today)
    reason = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    executor = relationship("ExecutorProfile", back_populates="days_off")
