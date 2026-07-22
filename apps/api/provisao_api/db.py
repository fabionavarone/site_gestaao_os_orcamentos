from sqlalchemy import MetaData, create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings

metadata = MetaData(naming_convention={"ix":"ix_%(column_0_label)s","uq":"uq_%(table_name)s_%(column_0_name)s","ck":"ck_%(table_name)s_%(constraint_name)s","fk":"fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s","pk":"pk_%(table_name)s"})
class Base(DeclarativeBase): metadata = metadata
database_url = settings().database_url
engine = create_engine(database_url, pool_pre_ping=True, connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {}, poolclass=StaticPool if database_url.endswith(":memory:") else None)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
