from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base for GenomAI's own application data, separate from inspected data."""
