import os
os.environ.setdefault("JWT_SECRET_KEY","test-only-jwt-secret-key-must-be-at-least-32-bytes-long")
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.dependencies import get_db
from main import app
from sqlalchemy import create_engine, text


TEST_DATABASE_URL = os.getenv("DATABASE_URL")

if not TEST_DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL must point to the test database when running tests."
    )


test_engine = create_engine(
    TEST_DATABASE_URL,
    pool_pre_ping=True,
)


TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)

@pytest.fixture(autouse=True)
def clean_database():
    with test_engine.begin() as connection:
        connection.execute(
            text(
                """
                DO $$
                DECLARE
                    table_record RECORD;
                BEGIN
                    FOR table_record IN
                        SELECT tablename
                        FROM pg_tables
                        WHERE schemaname = 'public'
                          AND tablename != 'alembic_version'
                    LOOP
                        EXECUTE format(
                            'TRUNCATE TABLE public.%I RESTART IDENTITY CASCADE',
                            table_record.tablename
                        );
                    END LOOP;
                END
                $$;
                """
            )
        )
        
@pytest.fixture
def db_session():
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()