"""Migration v1: initial schema for all Phase II tables.

Emits DDL from the authoritative ORM metadata (single source of truth for the
initial schema); subsequent migrations are explicit versioned deltas.
"""
from app.db import Base
from app import models_db  # noqa: F401  (register all models on Base)


def upgrade(conn):
    Base.metadata.create_all(bind=conn, checkfirst=True)
