import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.db import get_connection

def inspect_table(table_name: str, limit: int = 10):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {table_name} LIMIT {limit};")
            rows = cur.fetchall()
            print(f"\n=== Table: {table_name} ({len(rows)} records) ===")
            print(json.dumps(rows, default=str, indent=2))

def list_tables():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)
            tables = [row["table_name"] for row in cur.fetchall()]
            print("\n=== Database Tables in Public Schema ===")
            for t in tables:
                print(f" - {t}")

def main():
    parser = argparse.ArgumentParser(description="Inspect OnboardAI Database")
    parser.add_argument("--table", "-t", type=str, help="Table name to inspect")
    parser.add_argument("--limit", "-l", type=int, default=10, help="Row limit")
    args = parser.parse_args()

    if args.table:
        inspect_table(args.table, args.limit)
    else:
        list_tables()
        print("\nTip: Run with --table <name> (e.g. --table employee_assignments, payroll_profiles, employee_documents)")

if __name__ == "__main__":
    main()
