"""pytest 공통 설정.

통합 테스트(`@pytest.mark.integration`)는 기본적으로 건너뛴다. 실제 MySQL이
필요하기 때문이다. 돌리려면 전용 테스트 DB를 가리키는 환경변수를 준다:

    MEALFIT_TEST_DB_URL=mysql+pymysql://root:비번@localhost:3306/mealfit_it?charset=utf8mb4

⚠️ 이 DB의 restaurant/menu는 테스트가 지웠다 만들었다 한다. 운영·개발용
   mealfit_test를 절대 가리키지 말 것. 안전장치로 DB 이름에 'test'나 'it'이
   들어가지 않으면 실행을 거부한다.
"""

from __future__ import annotations

import os

import pytest

TEST_DB_ENV = "MEALFIT_TEST_DB_URL"

#: 실수로 운영 DB를 날리는 것을 막는 안전장치.
FORBIDDEN_DB_NAMES = {"mealfit_test", "mealfit", "mealfit_prod"}


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        f"integration: 실제 MySQL이 필요한 테스트. {TEST_DB_ENV} 설정 시에만 실행된다.",
    )


@pytest.fixture(scope="session")
def integration_db_url() -> str:
    url = os.environ.get(TEST_DB_ENV)
    if not url:
        pytest.skip(f"{TEST_DB_ENV} 미설정 — 통합 테스트를 건너뛴다")

    db_name = url.rsplit("/", 1)[-1].split("?")[0]
    if db_name in FORBIDDEN_DB_NAMES:
        pytest.fail(
            f"{TEST_DB_ENV}이 '{db_name}'을 가리킨다. 이 테스트는 테이블을 비우므로 "
            f"전용 DB를 써야 한다 (예: mealfit_it)."
        )
    return url


@pytest.fixture(scope="session")
def engine(integration_db_url):
    from sqlalchemy import create_engine

    eng = create_engine(integration_db_url, pool_pre_ping=True)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine):
    """테스트 1건 = 트랜잭션 1건. 끝나면 롤백해서 흔적을 남기지 않는다."""
    from sqlalchemy.orm import Session

    connection = engine.connect()
    transaction = connection.begin()
    s = Session(bind=connection)
    try:
        yield s
    finally:
        s.close()
        transaction.rollback()
        connection.close()
