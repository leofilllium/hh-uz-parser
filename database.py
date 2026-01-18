"""Database models and connection for HH.uz Telegram Bot."""
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config import DATABASE_URL

Base = declarative_base()


class User(Base):
    """Telegram user subscribed to vacancy notifications."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<User(telegram_id={self.telegram_id}, username={self.username})>"


class SeenVacancy(Base):
    """Vacancy that has already been sent to users."""
    __tablename__ = "seen_vacancies"
    
    id = Column(Integer, primary_key=True)
    vacancy_id = Column(String(50), unique=True, nullable=False, index=True)
    notified_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<SeenVacancy(vacancy_id={self.vacancy_id})>"


# Database engine and session
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Get a database session."""
    db = SessionLocal()
    try:
        return db
    finally:
        pass  # Session will be closed by caller


# User operations
def get_or_create_user(telegram_id: int, username: str = None, first_name: str = None) -> User:
    """Get existing user or create a new one."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if user:
            # Update username if changed
            if username and user.username != username:
                user.username = username
            if first_name and user.first_name != first_name:
                user.first_name = first_name
            user.is_active = True
            db.commit()
            db.refresh(user)
        else:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                is_active=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user
    finally:
        db.close()


def deactivate_user(telegram_id: int) -> bool:
    """Deactivate a user (stop notifications)."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if user:
            user.is_active = False
            db.commit()
            return True
        return False
    finally:
        db.close()


def get_active_users() -> list:
    """Get all active users."""
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.is_active == True).all()
        return [(u.telegram_id, u.username, u.first_name) for u in users]
    finally:
        db.close()


def get_users_count() -> tuple:
    """Get count of active and total users."""
    db = SessionLocal()
    try:
        total = db.query(User).count()
        active = db.query(User).filter(User.is_active == True).count()
        return active, total
    finally:
        db.close()


# Vacancy operations
def is_vacancy_seen(vacancy_id: str) -> bool:
    """Check if a vacancy has already been sent."""
    db = SessionLocal()
    try:
        exists = db.query(SeenVacancy).filter(SeenVacancy.vacancy_id == vacancy_id).first()
        return exists is not None
    finally:
        db.close()


def mark_vacancy_seen(vacancy_id: str) -> None:
    """Mark a vacancy as sent."""
    db = SessionLocal()
    try:
        if not is_vacancy_seen(vacancy_id):
            seen = SeenVacancy(vacancy_id=vacancy_id)
            db.add(seen)
            db.commit()
    finally:
        db.close()


def get_seen_vacancy_ids() -> set:
    """Get all seen vacancy IDs."""
    db = SessionLocal()
    try:
        vacancies = db.query(SeenVacancy.vacancy_id).all()
        return {v.vacancy_id for v in vacancies}
    finally:
        db.close()
