"""Engine et sessions SQLAlchemy. Aucune connexion n'est ouverte avant la première requête."""
from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import settings

engine = create_engine(settings.database_url, pool_size=settings.db_pool_size,
                       pool_pre_ping=True, echo=settings.db_echo)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Dépendance FastAPI : `db: Session = Depends(get_db)`."""
    with SessionLocal() as db:
        yield db


def ping() -> bool:
    """True si la base répond."""
    with engine.connect() as conn:
        return conn.execute(text("SELECT 1")).scalar() == 1
