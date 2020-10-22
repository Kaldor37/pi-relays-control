import secrets
import string
from datetime import datetime
from typing import Tuple, Optional

from sqlalchemy import Column, String, MetaData, Integer, DateTime, Boolean, func
# noinspection PyProtectedMember
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base

_Base = declarative_base()


class User(_Base):
    __tablename__ = 'user'

    _AUTH_TOKEN_SIZE = 256

    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=True)
    auth_token = Column(String(_AUTH_TOKEN_SIZE), nullable=True, index=True)
    admin = Column(Boolean, default=False)
    registered = Column(DateTime, default=datetime.now)
    registration_user_agent = Column(String(128), nullable=True)
    registration_ip = Column(String(45), nullable=True)
    access_granted = Column(DateTime, nullable=True)
    last_access = Column(DateTime, nullable=True)

    @classmethod
    def register(cls, session_factory, user_agent: str, ip: str):
        """
        Registers a new user (generates a new authentication token)
        """
        alphabet = string.ascii_letters + string.digits
        auth_token = ''.join(secrets.choice(alphabet) for __ in range(cls._AUTH_TOKEN_SIZE))

        user = cls(
            auth_token=auth_token,
            registration_user_agent=user_agent,
            registration_ip=ip
        )
        session = session_factory(expire_on_commit=False)
        session.add(user)
        session.commit()
        session.close()
        return user

    @classmethod
    def get_user(cls, session, **filters) -> Optional['User']:
        return session.query(User).filter_by(**filters).first()

    @classmethod
    def get_by_token(cls, auth_token: str, session_factory=None, session=None) -> Optional['User']:
        """
        Retrieves a user by its auth token
        """
        session = session or session_factory()
        user = cls.get_user(session, auth_token=auth_token)
        if session_factory:
            session.close()

        return user

    @classmethod
    def get_waiting_count(cls, session_factory):
        """
        Returns the total count of users waiting for their access to be granted
        """
        session = session_factory()
        users_count = session.query(User).filter_by(access_granted=None).count()
        session.close()
        return users_count

    @classmethod
    def grant_access(cls, session_factory, user_id: int):
        session = session_factory()
        user = cls.get_user(session, id=user_id)
        if not user:
            return False
        user.access_granted = datetime.now()
        session.commit()
        session.close()
        return True

    @classmethod
    def revoke_access(cls, session_factory, user_id: int):
        session = session_factory()
        user = cls.get_user(session, id=user_id)
        if not user:
            return False
        session.delete(user)
        session.commit()
        session.close()
        return True

    @classmethod
    def upgrade(cls, session_factory, user_id: int):
        session = session_factory()
        user = cls.get_user(session, id=user_id)
        if not user:
            return False
        user.admin = True
        session.commit()
        session.close()
        return True

    @classmethod
    def downgrade(cls, session_factory, user_id: int):
        session = session_factory()
        user = cls.get_user(session, id=user_id)
        if not user:
            return False
        user.admin = False
        session.commit()
        session.close()
        return True

    @classmethod
    def set_name(cls, session_factory, user_id: int, user_name: str):
        session = session_factory()
        user = cls.get_user(session, id=user_id)
        if not user:
            return False
        user.name = user_name
        session.commit()
        session.close()
        return True


_TABLES: Tuple[_Base] = (
    User,
)


def init_database(db_engine: Engine):
    """
    Creates missing tables in database
    """
    db_metadata = MetaData()
    db_metadata.reflect(db_engine)

    for table in _TABLES:
        if table.__table__.name not in db_metadata.tables:
            table.__table__.create(db_engine)
