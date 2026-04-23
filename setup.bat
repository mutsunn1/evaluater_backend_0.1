@echo off
set PGPASSWORD=postgres
"D:\PostgreSQL\18\bin\psql.exe" -U postgres -h 127.0.0.1 -c "SELECT 'exists' FROM pg_database WHERE datname='evaluator_db';" > nul 2>&1
if %errorlevel% equ 0 (
    echo Database already exists
) else (
    "D:\PostgreSQL\18\bin\psql.exe" -U postgres -h 127.0.0.1 -c "CREATE DATABASE evaluator_db;"
    echo Database created
)
