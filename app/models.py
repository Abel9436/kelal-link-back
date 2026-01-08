from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Text, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    username = Column(String, unique=True, index=True, nullable=True)
    profile_pic = Column(String, nullable=True)
    google_id = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    urls = relationship("URL", back_populates="user")
    bundles = relationship("Bundle", back_populates="user")
    
    # Collaboration Logic
    owned_collaborations = relationship("Collaboration", foreign_keys="[Collaboration.owner_id]", back_populates="owner")
    joined_collaborations = relationship("Collaboration", foreign_keys="[Collaboration.collaborator_id]", back_populates="collaborator")

class URL(Base):
    __tablename__ = "urls"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    long_url = Column(String, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)
    clicks = Column(Integer, default=0)
    is_cloaked = Column(Boolean, default=False) # Stealth Mode Protocol
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
    theme_color = Column(String, default="#00f2ff")
    bg_color = Column(String, default="#0a0a0a")
    text_color = Column(String, default="#888888")
    title_color = Column(String, default="#ffffff")
    card_color = Column(String, default="rgba(255,255,255,0.05)")
    bg_image = Column(String, nullable=True)
    profile_image = Column(String, nullable=True)
    access_level = Column(String, default="restricted") # restricted, view, edit
    clicks = Column(Integer, default=0)
    is_cloaked = Column(Boolean, default=False) # Stealth Mode Protocol
    max_clicks = Column(Integer, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    password = Column(String, nullable=True)
    meta_title = Column(String, nullable=True)
    meta_description = Column(String, nullable=True)
    manager_token = Column(String, unique=True, index=True, nullable=True)
    analyst_token = Column(String, unique=True, index=True, nullable=True)
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
    device_type = Column(String, nullable=True)

    # Relationships
    url = relationship("URL", back_populates="analytics")
    bundle = relationship("Bundle", back_populates="analytics")

class Collaboration(Base):
    __tablename__ = "collaborations"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    collaborator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    bundle_id = Column(Integer, ForeignKey("bundles.id"), nullable=True) # Specific studio link
    role = Column(String, default="manager") # manager, analyst
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", foreign_keys=[owner_id], back_populates="owned_collaborations")
    collaborator = relationship("User", foreign_keys=[collaborator_id], back_populates="joined_collaborations")
    bundle = relationship("Bundle")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(String) # invitation, system
    title = Column(String)
    message = Column(String)
    is_read = Column(Boolean, default=False)
    link = Column(String, nullable=True) # Optional link to the studio/drop
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="notifications")

User.notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
