import asyncio
import sys
import os
os.environ["PYTHONIOENCODING"] = "utf-8"

async def main():
    import asyncpg
    try:
        conn = await asyncpg.connect(
            host="127.0.0.1",
            port=5432,
            user="postgres",
            password="postgres",
            database="postgres",
        )
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = 'evaluator_db'")
        if not exists:
            await conn.execute("CREATE DATABASE evaluator_db")
            print("OK: database created")
        else:
            print("OK: database already exists")
        await conn.close()
    except Exception as e:
        print(f"FAIL: {e}")

asyncio.run(main())
