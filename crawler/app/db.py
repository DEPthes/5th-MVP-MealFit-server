"""SQLAlchemy 엔진·세션. Spring이 만든 restaurant/menu 스키마를 그대로 쓴다.

이 모듈은 테이블을 만들지 않는다(Spring ddl-auto가 기본 골격을 만든다).
8번 파이프라인이 소유하는 추가 컬럼·인덱스는 sql/schema_additions.sql로
별도 관리한다.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.settings import settings

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(settings.sqlalchemy_url, pool_pre_ping=True)
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    """식당 1건 = 트랜잭션 1건. 실패 시 그 식당만 롤백된다."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
