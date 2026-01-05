from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Text, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    profile_pic = Column(String, nullable=True)
    google_id = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    urls = relationship("URL", back_populates="user")
    bundles = relationship("Bundle", back_populates="user")

class URL(Base):
    __tablename__ = "urls"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    long_url = Column(String, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)
    clicks = Column(Integer, default=0)
    max_clicks = Column(Integer, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    password = Column(String, nullable=True)
    meta_title = Column(String, nullable=True)
    meta_description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="urls")
    analytics = relationship("Click", back_populates="url", cascade="all, delete-orphan")

class Bundle(Base):
    __tablename__ = "bundles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    slug = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    items = Column(JSON, nullable=False)
    theme_color = Column(String, default="#00f2ff") # Default to neonatal cyan
    bg_color = Column(String, default="#0a0a0a") # Default to studio black
    text_color = Column(String, default="#888888") # Default to primary muted
    title_color = Column(String, default="#ffffff") # Default to contrast white
    card_color = Column(String, default="rgba(255,255,255,0.05)") # Default to subtle glass
    clicks = Column(Integer, default=0)
    max_clicks = Column(Integer, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    password = Column(String, nullable=True)
    meta_title = Column(String, nullable=True)
    meta_description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="bundles")
    analytics = relationship("Click", back_populates="bundle", cascade="all, delete-orphan")

class Click(Base):
    __tablename__ = "clicks"

    id = Column(Integer, primary_key=True, index=True)
    url_id = Column(Integer, ForeignKey("urls.id"), nullable=True)
    bundle_id = Column(Integer, ForeignKey("bundles.id"), nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    referer = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    device_type = Column(String, nullable=True) # Mobile, Desktop, Tablet

    # Relationships
    url = relationship("URL", back_populates="analytics")
    bundle = relationship("Bundle", back_populates="analytics")
