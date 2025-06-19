from typing import List, Optional

from sqlalchemy import CheckConstraint, Column, DateTime, Enum, ForeignKeyConstraint, Index, Integer, String, TIMESTAMP, Table, Text, text, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import datetime

class Base(DeclarativeBase):
    pass


class Authors(Base):
    __tablename__ = 'authors'

    author_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    bio: Mapped[Optional[str]] = mapped_column(Text)

    books: Mapped[List['Books']] = relationship('Books', back_populates='author')


class Categories(Base):
    __tablename__ = 'categories'

    category_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))

    book: Mapped[List['Books']] = relationship('Books', secondary='book_categories', back_populates='category')


class Users(Base):
    __tablename__ = 'users'
    __table_args__ = (
        Index('email', 'email', unique=True),
        Index('username', 'username', unique=True),
        Index('username_2', 'username', unique=True)
    )

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fullname: Mapped[str] = mapped_column(String(100))
    username: Mapped[str] = mapped_column(String(50))
    email: Mapped[str] = mapped_column(String(100))
    password: Mapped[str] = mapped_column(String(255))
    age: Mapped[Optional[int]] = mapped_column(Integer)
    role: Mapped[Optional[str]] = mapped_column(Enum('reader', 'admin'), server_default=text("'reader'"))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    ratings: Mapped[List['Ratings']] = relationship('Ratings', back_populates='user')
    reading_history: Mapped[List['ReadingHistory']] = relationship('ReadingHistory', back_populates='user')


class Books(Base):
    __tablename__ = 'books'
    __table_args__ = (
        ForeignKeyConstraint(['author_id'], ['authors.author_id'], name='books_ibfk_1'),
        Index('author_id', 'author_id')
    )

    book_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    author_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('authors.author_id'))
    cover_url: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    file_url: Mapped[Optional[str]] = mapped_column(String(255))
    published_year: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    author: Mapped[Optional['Authors']] = relationship('Authors', back_populates='books')
    category: Mapped[List['Categories']] = relationship('Categories', secondary='book_categories', back_populates='book')
    reading_history: Mapped[List['ReadingHistory']] = relationship('ReadingHistory', back_populates='book')
    ratings: Mapped[List['Ratings']] = relationship('Ratings', back_populates='book', cascade='all, delete-orphan')

t_book_categories = Table(
    'book_categories', Base.metadata,
    Column('book_id', Integer, primary_key=True, nullable=False),
    Column('category_id', Integer, primary_key=True, nullable=False),
    ForeignKeyConstraint(['book_id'], ['books.book_id'], ondelete='CASCADE', name='book_categories_ibfk_1'),
    ForeignKeyConstraint(['category_id'], ['categories.category_id'], ondelete='CASCADE', name='book_categories_ibfk_2'),
    Index('category_id', 'category_id')
)


class Ratings(Base):
    __tablename__ = 'ratings'
    __table_args__ = (
        CheckConstraint('rating BETWEEN 1 AND 5', name='ratings_chk_1'),
        Index('idx_ratings_user_id', 'user_id'),
    )

    rating_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, nullable=False)
    book_id: Mapped[int] = mapped_column(Integer, ForeignKey('books.book_id'), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('users.user_id'), nullable=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)

    # Quan hệ
    user: Mapped[Optional['Users']] = relationship('Users', back_populates='ratings')
    book: Mapped['Books'] = relationship('Books', back_populates='ratings')

class ReadingHistory(Base):
    __tablename__ = 'reading_history'
    __table_args__ = (
        ForeignKeyConstraint(['book_id'], ['books.book_id'], name='reading_history_ibfk_2'),
        ForeignKeyConstraint(['user_id'], ['users.user_id'], name='reading_history_ibfk_1'),
        Index('book_id', 'book_id')
    )

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_position: Mapped[Optional[int]] = mapped_column(Integer)
    last_read_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)

    book: Mapped['Books'] = relationship('Books', back_populates='reading_history')
    user: Mapped['Users'] = relationship('Users', back_populates='reading_history')
