import os
from sqlalchemy import create_engine, inspect

url = os.getenv("DATABASE_URL") or os.getenv("DALIL_DATABASE_URL")
if not url:
    raise SystemExit("Neither DATABASE_URL nor DALIL_DATABASE_URL is set.")

engine = create_engine(url)
insp = inspect(engine)

schemas = [
    s for s in insp.get_schema_names()
    if s not in ("information_schema",) and not s.startswith("pg_")
]

print("SCHEMAS AND TABLES")
for schema in schemas:
    tables = insp.get_table_names(schema=schema)
    if not tables:
        continue
    print(f"\n[{schema}]")
    for table in tables:
        print(f" - {table}")

print("\nLIKELY HADITH TABLES")
for schema in schemas:
    for table in insp.get_table_names(schema=schema):
        name = table.lower()
        if any(k in name for k in ("hadith", "entry", "record")):
            print(f"\n=== {schema}.{table} ===")
            for col in insp.get_columns(table, schema=schema):
                print(" -", col["name"])