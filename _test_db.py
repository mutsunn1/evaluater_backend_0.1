import asyncio
import asyncpg

async def main():
    try:
        conn = await asyncpg.connect(
            host="127.0.0.1",
            port=5432,
            user="postgres",
            password="postgres",
            database="postgres",
        )
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", "evaluator_db")
        if not exists:
            await conn.execute("CREATE DATABASE evaluator_db")
            print("OK: database created")
        else:
            print("OK: database already exists")
        await conn.close()
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}")

asyncio.run(main())
