import os
import sys
import getpass
import oracledb
import time
from pathlib import Path

# user config
CONFIG = {
    "db_user": "SYSTEM",
    "db_dsn": "localhost:1521/XEPDB1", # host:port/service_name
    "output_dir": "./output",
    "batch_size": 100,
    "chunk_size": 65536, # 64KB read chunks
}

# db connection
def get_connection(): 
    password = os.environ.get("DB_PASSWORD") or getpass.getpass("Oracle password: ")
    try: 
        conn = oracledb.connect(
            user = CONFIG["db_user"],
            password = password,
            dsn = CONFIG["db_dsn"]
        )  
        print(f"Connected to {CONFIG['db_dsn']}")
        return conn
    except oracledb.Error as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

def discover_blob_columns(conn):
    query = """
        SELECT owner, table_name, column_name
        FROM all_tab_columns
        WHERE data_type = 'BLOB'
          AND owner NOT IN ('SYS','XDB','DBSNMP','OJVMSYS',
                            'AUDSYS','GSMADMIN_INTERNAL','ORACLE_OCM')
        ORDER BY owner, table_name, column_name
    """
    with conn.cursor() as cursor:
        cursor.execute(query)
        results = cursor.fetchall()
        if not results:
            print("No BLOB columns found in non-system schemas.")
            sys.exit(0)
        print(f"Found {len(results)} BLOB column(s):")
        for owner, table, col in results:
            print(f"  {owner}.{table}.{col}")
    return results

# extract PDFs (the exciting bit!)
pdf_magic = b"%PDF"

def extract_pdfs(conn, columns):
    out_dir = Path(CONFIG["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    start = time.time()
    total = 0
    total_bytes = 0

    for owner, table, col in columns:
        pk_col = find_pk(conn, owner, table)
        query = f'SELECT {pk_col}, "{col}" FROM "{owner}"."{table}" WHERE "{col}" IS NOT NULL'
        print(f"\nScanning: {owner}.{table}.{col}...")

        with conn.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()
            found = 0
            skipped = 0
            for pk_val, blob in rows:
                if not blob:
                    skipped += 1
                    continue

                raw = blob if isinstance(blob, bytes) else blob.read()
                if raw[:4] != pdf_magic:
                    skipped += 1
                    continue

                filepath = out_dir / f"{table}_{pk_val}_{col}.pdf"
                with open(filepath, "wb") as f:
                    f.write(raw)
                total += 1
                total_bytes += len(raw)
                found += 1
                size_kb = len(raw) / 1024
                print(f"  [{total}] PDF found ({size_kb:.1f}KB) → {filepath.name}")

            if skipped:
                print(f"  Skipped {skipped} row(s) (not PDF)")

    elapsed = time.time() - start
    total_mb = total_bytes / (1024 * 1024)
    print(f"\nDone in {elapsed:.1f}s | {total} PDF(s), {total_mb:.2f}MB extracted → {out_dir}")
    
def find_pk(conn, owner, table):
    query = """
        SELECT cols.column_name
        FROM all_constraints cons, all_cons_columns cols
        WHERE cons.constraint_type = 'P'
          AND cons.owner = cols.owner
          AND cons.constraint_name = cols.constraint_name
          AND cols.owner = :owner_name
          AND cols.table_name = :table_name
    """
    with conn.cursor() as cursor:
        cursor.execute(query, owner_name=owner, table_name=table)
        row = cursor.fetchone()
        if row:
            return row[0]
        return "ROWID"
    
if __name__ == "__main__":
    conn = get_connection()
    try:
        columns = discover_blob_columns(conn)
        extract_pdfs(conn, columns)
    finally:
        conn.close()
        print("Connection closed.")
        