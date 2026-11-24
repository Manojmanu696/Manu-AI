from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def enforce_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



def install_integrity_guards():
    """Enforce rating and status bounds for existing SQLite databases."""
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as connection:
        for operation in ("INSERT", "UPDATE"):
            connection.exec_driver_sql(f"""
                CREATE TRIGGER IF NOT EXISTS validate_media_{operation.lower()}
                BEFORE {operation} ON media_items
                WHEN NEW.status NOT IN ('unknown', 'unwatched', 'want', 'current', 'completed', 'dropped', 'on_hold', 'recommended')
                  OR NEW.personal_rating IS NOT NULL AND (
                    typeof(NEW.personal_rating) NOT IN ('integer', 'real') OR NEW.personal_rating < 1 OR NEW.personal_rating > 10
                  )
                BEGIN
                    SELECT RAISE(ABORT, 'Invalid media rating or viewing status');
                END
            """)
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS local_ai_kind_created_idx ON local_ai_records(kind, created_at)"
        )
