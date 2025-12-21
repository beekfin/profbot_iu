import asyncpg
from os import getenv


class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(
            user=getenv("DB_USER"),
            password=getenv("DB_PASSWORD"),
            database=getenv("DB_NAME"),
            host="localhost",
            port=int(getenv("DB_PORT"))
        )

    async def close(self):
        if self.pool:
            await self.pool.close()

    async def execute(self, query: str, *args):
        async with self.pool.acquire() as connection:
            return await connection.execute(query, *args)

    async def fetch(self, query: str, *args):
        async with self.pool.acquire() as connection:
            return await connection.fetch(query, *args)

    async def fetchrow(self, query: str, *args):
        async with self.pool.acquire() as connection:
            return await connection.fetchrow(query, *args)

    async def fetchval(self, query: str, *args):
        async with self.pool.acquire() as connection:
            return await connection.fetchval(query, *args)


db = Database()
