import os
import sys
import getpass
import oracledb
from pathlib import Path

# user config
CONFIG = {
    "db_user": "your_username",
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
          AND owner NOT IN ('SYS','SYSTEM','XDB','DBSNMP','OJVMSYS',
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

    total = 0

    for owner, table, col in columns:
        pk_col = find_pk(conn, owner, table)
        query = f'SELECT {pk_col}, "{col}" FROM "{owner}"."{table}" WHERE "{col}" IS NOT NULL'

        with conn.cursor() as cursor:
            cursor.execute(query)
            while True:
                rows = cursor.fetchmany(CONFIG["batch_size"])
                if not rows:
                    break
                for row in rows:
                    pk_val, blob = row
                    if not blob:
                        continue
                    header = blob.read(5)
                    if header != pdf_magic:
                        continue

                    filename = f"{table}_{pk_val}_{col}.pdf"
                    filename = out_dir / filename
                    with open(filename, "wb") as f:
                        f.write(header)
                        while chunk:= blob.read(CONFIG["chunk_size"]):
                            f.write(chunk)
                        total += 1
                        print(f" [{total}] Saved: {filename}")
    print(f"\nDone. {total} PDF(s) extracted to {out_dir}")

def find_pk(conn, owner, table):
    query = """
        SELECT cols.column_name
        FROM all_constraints cons, all_cons_columns cols
        WHERE cons.constraint_type = 'P'
          AND cons.owner = cols.owner
          AND cons.constraint_name = cols.constraint_name
          AND cols.owner = :owner
          AND cols.table_name = :table
    """
    with conn.cursor() as cursor:
        cursor.execute(query, owner=owner, table=table)
        row = cursor.fetchone()
        if row:
            return row[0]
        return "ROWID"  # fallback
    
if __name__ == "__main__":
    conn = get_connection()
    try:
        columns = discover_blob_columns(conn)
        extract_pdfs(conn, columns)
    finally:
        conn.close()
        print("Connection closed.")