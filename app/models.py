from sqlalchemy import Column, String, Integer, DateTime, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()

class Url(Base):
    __tablename__ = "urls"
    
    id = Column(String, primary_key=True)
    original_url = Column(String, unique=True, nullable=False)
    short_code = Column(String(6), unique=True, nullable=False)
    title = Column(String, nullable=True)
    click_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_original_url', 'original_url'),
        Index('idx_short_code', 'short_code'),
    )