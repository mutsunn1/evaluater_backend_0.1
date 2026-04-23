from sqlalchemy import create_engine, text

url = "postgresql+pg8000://postgres:0112@127.0.0.1:5432/postgres"
engine = create_engine(url, isolation_level="AUTOCOMMIT")
with engine.connect() as conn:
    exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname='evaluator_db'")).scalar()
    if not exists:
        conn.execute(text("CREATE DATABASE evaluator_db"))
        print("OK: database 'evaluator_db' created")
    else:
        print("OK: database 'evaluator_db' already exists")
engine.dispose()
