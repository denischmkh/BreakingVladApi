from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Type, Any, AsyncGenerator, Iterable
from uuid import UUID
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from .db_connect import AsyncSessionLocal
from .models import Base, User, Product, Category, Basket
from pydantic import BaseModel
import sqlalchemy as _sql
from fastapi.exceptions import HTTPException
from routers.schemas import (UserReadSchema,
                             UserCreateSchema,
                             UserDatabaseSchema,
                             CategoryReadSchema,
                             CategoryCreateSchema,
                             ProductCreateSchema,
                             ProductReadSchema,
                             BasketCreateSchema,
                             BasketReadSchema, UserAuthScheme, )
from .dependencies import verify_password, get_password_hash


async def session_generator() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


# Context manager to get session
@asynccontextmanager
async def get_session() -> AsyncSession:
    async for session in session_generator():
        try:
            async with session.begin():
                yield session
        finally:
            await session.close()


############################################################################
#              Abstract class to give an example for child class           #
############################################################################

class BaseCRUD(ABC):
    """ Every child class must contain his SQLAlchemy model to interact with her """
    __db_model = Type[Base]

    @classmethod
    @abstractmethod
    async def create(cls, pydantic_schema: Type[BaseModel]) -> Any:
        """ Create new record by using pydantic model """
        ...

    @classmethod
    @abstractmethod
    async def read(cls) -> Any:
        """ Read record """
        ...

    @classmethod
    @abstractmethod
    async def delete(cls, **kwargs) -> Any:
        """ Delete record """
        ...


class UserCRUD(BaseCRUD):
    """ Controlling interaction with User """
    __db_model = User

    @classmethod
    async def create(cls, user_create_schema: UserCreateSchema) -> UserDatabaseSchema:
        async with get_session() as session:
            stmt = _sql.select(cls.__db_model).where(cls.__db_model.username == user_create_schema.username)
            result = await session.execute(stmt)
            existing_user: User = result.scalars().first()
            if existing_user:
                raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail='Username already exists')
            stmt = _sql.select(cls.__db_model).where(cls.__db_model.email == user_create_schema.email)
            result = await session.execute(stmt)
            existing_user_email = result.scalars().first()
            if existing_user_email:
                raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail='Email already exists')
            hashed_password = get_password_hash(user_create_schema.password)
            user_database_schema = UserDatabaseSchema(**user_create_schema.dict(), hashed_password=hashed_password)
            new_user = cls.__db_model(
                **user_database_schema.dict(),
            )
            session.add(new_user)
            await session.commit()
            return user_database_schema

    @classmethod
    async def read(cls, user_id: UUID | None, username: str | None) -> UserReadSchema | None:
        async with get_session() as session:
            if user_id or username:
                stmt = _sql.select(cls.__db_model).where(
                    _sql.or_(cls.__db_model.username == username, cls.__db_model.id == user_id))
            else:
                return None
            result = await session.execute(stmt)
            user: User = result.scalars().first()
            if user is None:
                return user
            return user

    @classmethod
    async def delete(cls, user_id: UUID) -> UserReadSchema | None:
        async with get_session() as session:
            stmt = _sql.select(cls.__db_model).where(cls.__db_model.id == user_id)
            result = await session.execute(stmt)
            user: User = result.scalars().first()
            if user is None:
                return user
            delete_stmt = _sql.delete(cls.__db_model).where(cls.__db_model.id == user_id)
            await session.execute(delete_stmt)
            return user

    @classmethod
    async def get_all_users(cls):
        async with get_session() as session:
            stmt = _sql.select(cls.__db_model)
            result = await session.execute(stmt)
            users = result.scalars().all()
            print(users)
            return users

    @classmethod
    async def verify_user(cls, user_data: OAuth2PasswordRequestForm) -> UserReadSchema | None:
        async with get_session() as session:
            stmt = _sql.select(cls.__db_model).where(cls.__db_model.username == user_data.username)
            result = await session.execute(stmt)
            user: User = result.scalars().first()
            if not user:
                return None
            verify: bool = verify_password(password=user_data.password, hashed_password=user.hashed_password)
            if not verify:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Incorrect password')
            return user

    @classmethod
    async def ban_user(cls, user_id: UUID) -> UserReadSchema:
        async with get_session() as session:
            stmt = _sql.select(cls.__db_model).where(cls.__db_model.id == user_id)
            result = await session.execute(stmt)
            user: User = result.scalars().first()
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
            if not user.active:
                raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail='User already banned')
            stmt = _sql.update(cls.__db_model).where(cls.__db_model.id == user_id).values(active=False)
            await session.execute(stmt)
            await session.commit()
        async with get_session() as session:
            stmt = _sql.select(cls.__db_model).where(cls.__db_model.id == user_id)
            result = await session.execute(stmt)
            user: User = result.scalars().first()
            return user

    @classmethod
    async def unban_user(cls, user_id: UUID) -> UserReadSchema:
        async with get_session() as session:
            stmt = _sql.select(cls.__db_model).where(cls.__db_model.id == user_id)
            result = await session.execute(stmt)
            user: User = result.scalars().first()
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
            if user.active:
                raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail='User already unbanned')
            stmt = _sql.update(cls.__db_model).where(cls.__db_model.id == user_id).values(active=True)
            await session.execute(stmt)
            await session.commit()
        async with get_session() as session:
            stmt = _sql.select(cls.__db_model).where(cls.__db_model.id == user_id)
            result = await session.execute(stmt)
            user: User = result.scalars().first()
            return user


class CategoryCRUD(BaseCRUD):
    __db_model = Category

    @classmethod
    async def create(cls, category_create_schema: CategoryCreateSchema) -> CategoryCreateSchema:
        async with get_session() as session:
            stmt = _sql.select(cls.__db_model).where(cls.__db_model.title == category_create_schema.title)
            request = await session.execute(statement=stmt)
            result = request.scalars().first()
            if result:
                raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail='Category already exist')
            stmt = _sql.insert(cls.__db_model).values(**category_create_schema.dict())
            await session.execute(statement=stmt)
            return category_create_schema

    @classmethod
    async def read(cls) -> Iterable:
        async with get_session() as session:
            stmt = _sql.select(cls.__db_model)
            result = await session.execute(stmt)
            categories = result.scalars().all()
            return categories

    @classmethod
    async def delete(cls, category_id: UUID) -> CategoryReadSchema | None:
        async with get_session() as session:
            stmt = _sql.select(cls.__db_model).where(cls.__db_model.id == category_id)
            result = await session.execute(stmt)
            category_schema: Category = result.scalars().first()
            if not category_schema:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Category not found!')
            delete_stmt = _sql.delete(cls.__db_model).where(cls.__db_model.id == category_id)
            await session.execute(delete_stmt)
            return category_schema
