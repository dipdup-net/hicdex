import asyncio
import decimal
import hashlib
import importlib
import logging
from contextlib import asynccontextmanager
from contextlib import suppress
from os.path import dirname
from os.path import join
from pathlib import Path
from typing import Any
from typing import AsyncIterator
from typing import Iterator
from typing import Optional
from typing import Tuple
from typing import Type

import sqlparse  # type: ignore
from tortoise import Model
from tortoise import Tortoise
from tortoise.backends.asyncpg.client import AsyncpgDBClient
from tortoise.backends.base.client import BaseDBAsyncClient
from tortoise.backends.base.client import TransactionContext
from tortoise.backends.sqlite.client import SqliteClient
from tortoise.fields import DecimalField
from tortoise.transactions import in_transaction
from tortoise.utils import get_schema_sql

from dipdup.exceptions import DatabaseConfigurationError
from dipdup.utils import iter_files
from dipdup.utils import pascal_to_snake

_logger = logging.getLogger('dipdup.database')
_truncate_schema_sql = Path(join(dirname(__file__), 'truncate_schema.sql')).read_text()


@asynccontextmanager
async def tortoise_wrapper(url: str, models: Optional[str] = None, timeout: int = 60) -> AsyncIterator:
    """Initialize Tortoise with internal and project models, close connections when done"""
    modules = {'int_models': ['dipdup.models']}
    if models:
        modules['models'] = [models]
    try:
        for attempt in range(timeout):
            try:
                await Tortoise.init(
                    db_url=url,
                    modules=modules,  # type: ignore
                )
            except OSError:
                _logger.warning('Can\'t establish database connection, attempt %s/%s', attempt, timeout)
                if attempt == timeout - 1:
                    raise
                await asyncio.sleep(1)
            else:
                break
        yield
    finally:
        await Tortoise.close_connections()


@asynccontextmanager
async def in_global_transaction():
    """Enforce using transaction for all queries inside wrapped block. Works for a single DB only."""
    async with in_transaction() as conn:
        conn: TransactionContext
        original_conn = Tortoise._connections['default']
        Tortoise._connections['default'] = conn

        if isinstance(original_conn, SqliteClient):
            conn.filename = original_conn.filename
            conn.pragmas = original_conn.pragmas
        elif isinstance(original_conn, AsyncpgDBClient):
            conn._pool = original_conn._pool
            conn._template = original_conn._template
        else:
            raise NotImplementedError

        yield

    Tortoise._connections['default'] = original_conn


def is_model_class(obj: Any) -> bool:
    """Is subclass of tortoise.Model, but not the base class"""
    return isinstance(obj, type) and issubclass(obj, Model) and obj != Model and not getattr(obj.Meta, 'abstract', False)


def iter_models(package: str) -> Iterator[Tuple[str, Type[Model]]]:
    """Iterate over built-in and project's models"""
    dipdup_models = importlib.import_module('dipdup.models')
    package_models = importlib.import_module(f'{package}.models')

    for models in (dipdup_models, package_models):
        for attr in dir(models):
            model = getattr(models, attr)
            if is_model_class(model):
                app = 'int_models' if models.__name__ == 'dipdup.models' else 'models'
                yield app, model


def set_decimal_context(package: str) -> None:
    """Adjust system decimal context to match database precision"""
    context = decimal.getcontext()
    prec = context.prec
    for _, model in iter_models(package):
        for field in model._meta.fields_map.values():
            if isinstance(field, DecimalField):
                prec = max(prec, field.max_digits)

    if context.prec < prec:
        _logger.warning('Decimal context precision has been updated: %s -> %s', context.prec, prec)
        context.prec = prec
        # NOTE: DefaultContext used for new threads
        decimal.DefaultContext.prec = prec
        decimal.setcontext(context)


def get_schema_hash(conn: BaseDBAsyncClient) -> str:
    """Get hash of the current schema"""
    schema_sql = get_schema_sql(conn, False)
    # NOTE: Column order could differ in two generated schemas for the same models, drop commas and sort strings to eliminate this
    processed_schema_sql = '\n'.join(sorted(schema_sql.replace(',', '').split('\n'))).encode()
    return hashlib.sha256(processed_schema_sql).hexdigest()


async def create_schema(conn: BaseDBAsyncClient, name: str) -> None:
    if isinstance(conn, SqliteClient):
        raise NotImplementedError

    await conn.execute_script(f'CREATE SCHEMA IF NOT EXISTS {name}')
    # FIXME: Oh...
    await conn.execute_script(_truncate_schema_sql)


async def execute_sql_scripts(conn: BaseDBAsyncClient, path: str) -> None:
    for file in iter_files(path, '.sql'):
        _logger.info('Executing `%s`', file.name)
        sql = file.read()
        for statement in sqlparse.split(sql):
            # NOTE: Ignore empty statements
            with suppress(AttributeError):
                await conn.execute_script(statement)


async def generate_schema(conn: BaseDBAsyncClient, name: str) -> None:
    if isinstance(conn, SqliteClient):
        await Tortoise.generate_schemas()
    elif isinstance(conn, AsyncpgDBClient):
        await create_schema(conn, name)
        await Tortoise.generate_schemas()

        # NOTE: Apply built-in scripts before project ones
        sql_path = join(dirname(__file__), '..', 'sql', 'on_reindex')
        await execute_sql_scripts(conn, sql_path)
    else:
        raise NotImplementedError


async def truncate_schema(conn: BaseDBAsyncClient, name: str) -> None:
    if isinstance(conn, SqliteClient):
        raise NotImplementedError

    await conn.execute_script(_truncate_schema_sql)
    await conn.execute_script(f"SELECT truncate_schema('{name}')")


async def wipe_schema(conn: BaseDBAsyncClient, name: str, immune_tables: Tuple[str, ...]) -> None:
    if isinstance(conn, SqliteClient):
        raise NotImplementedError

    immune_schema_name = f'{name}_immune'
    if immune_tables:
        await create_schema(conn, immune_schema_name)
        for table in immune_tables:
            await move_table(conn, table, name, immune_schema_name)

    await truncate_schema(conn, name)

    if immune_tables:
        for table in immune_tables:
            await move_table(conn, table, immune_schema_name, name)
        await drop_schema(conn, immune_schema_name)


async def drop_schema(conn: BaseDBAsyncClient, name: str) -> None:
    if isinstance(conn, SqliteClient):
        raise NotImplementedError

    await conn.execute_script(f'DROP SCHEMA IF EXISTS {name}')


async def move_table(conn: BaseDBAsyncClient, name: str, schema: str, new_schema: str) -> None:
    """Move table from one schema to another"""
    if isinstance(conn, SqliteClient):
        raise NotImplementedError

    await conn.execute_script(f'ALTER TABLE {schema}.{name} SET SCHEMA {new_schema}')


def prepare_models(package: str) -> None:
    for _, model in iter_models(package):
        # NOTE: Generate missing table names before Tortoise does
        model._meta.db_table = model._meta.db_table or pascal_to_snake(model.__name__)


def validate_models(package: str) -> None:
    """Check project's models for common mistakes"""
    for _, model in iter_models(package):
        table_name = model._meta.db_table

        if table_name != pascal_to_snake(table_name):
            raise DatabaseConfigurationError('Table name must be in snake_case', model)

        for field in model._meta.fields_map.values():
            field_name = field.model_field_name

            if field_name != pascal_to_snake(field_name):
                raise DatabaseConfigurationError('Model fields must be in snake_case', model)

            # NOTE: Leads to GraphQL issues
            if field_name == table_name:
                raise DatabaseConfigurationError('Model fields must differ from table name', model)
