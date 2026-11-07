@echo off
echo ===================================================
echo Starting PostgreSQL cluster at data\pgdata...
echo ===================================================
"C:\Program Files\PostgreSQL\17\bin\pg_ctl.exe" -D "%~dp0data\pgdata" -l "%~dp0data\pgdata\logfile" start
timeout /t 2 >nul
"C:\Program Files\PostgreSQL\17\bin\pg_isready.exe" -h 127.0.0.1 -p 5432
pause

