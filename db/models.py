from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, TIMESTAMP, BigInteger, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from sqlalchemy.sql import func

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String)
    balance = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    subscription_start = Column(TIMESTAMP, nullable=True)
    subscription_end = Column(TIMESTAMP, nullable=True)
    is_active = Column(Boolean, default=True)
    vpn_link = Column(String, nullable=True)
    server_id = Column(Integer, ForeignKey('servers.id'), nullable=True)  # Убираем default и делаем nullable
    
    # Поле для отслеживания использования пробного периода
    trial_used = Column(Boolean, default=False, nullable=False)  # Использовал ли пробный период
    
    # Связь с сервером
    server = relationship("Server", back_populates="users")

class Server(Base):
    __tablename__ = 'servers'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)  # Название сервера
    url = Column(String, nullable=False)   # URL API сервера
    is_active = Column(Boolean, default=True)  # Доступен ли сервер для новых пользователей
    is_default = Column(Boolean, default=False)  # Является ли сервером по умолчанию
    created_at = Column(DateTime, default=datetime.utcnow)
    description = Column(String, nullable=True)  # Описание сервера
    
    # Связь с пользователями
    users = relationship("User", back_populates="server")

class Payment(Base):
    __tablename__ = 'payments'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    amount = Column(Float, nullable=True)
    payment_id = Column(String, unique=True)  # ID платежа от donate.stream
    status = Column(String, default='pending')
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    nickname = Column(String)
    message = Column(String)
    pay_system = Column(String)
