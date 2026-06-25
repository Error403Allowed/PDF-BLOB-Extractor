# PDF BLOB Extractor

Extracts PDF documents stored as BLOBs in an Oracle Database.

## Requirements

- Python 3.8+
- `oracledb` package (`pip install oracledb`)
- Network access to an Oracle Database

## Setup

```bash
pip install oracledb
Configuration
Edit the CONFIG dict at the top of extract_pdfs.py:
Key
db_user
db_dsn
output_dir
batch_size
chunk_size
Usage
# Set password via env var (recommended)
export DB_PASSWORD=your_password
python extract_pdfs.py

# Or type it when prompted
python extract_pdfs.py
How It Works
1. Connects to Oracle in thin mode (no Oracle client needed)
2. Discovers all BLOB columns across non-system schemas
3. For each column, streams rows in batches
4. Checks the first 5 bytes of each BLOB for %PDF (PDF magic marker)
5. Saves matching BLOBs as .pdf files to the output directory
6. Names files as {table}_{pk}_{column}.pdf
Notes
- Uses python-oracledb thin mode — no Oracle Instant Client required
- BLOBs are streamed in chunks — handles large files without loading them entirely into memory
- Primary key is detected automatically; falls back to Oracle ROWID if none is defined
- Only extracts actual PDFs (validates the file header) — non-PDF BLOBs are skipped

## Disclaimer
Note on Documentation: This README was generated with the assistance of AI. The underlying project code is entirely human-written. The text has been reviewed and verified for accuracy, but please refer to the source code as the final authority on functionality.