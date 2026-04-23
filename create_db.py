import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        host="localhost",
        port=5432,
        user="postgres",
        password="postgres",
        database="postgres",
    )
    exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", "evaluator_db")
    if not exists:
        await conn.execute("CREATE DATABASE evaluator_db")
        print("Database 'evaluator_db' created successfully")
    else:
        print("Database 'evaluator_db' already exists")
    await conn.close()

asyncio.run(main())
