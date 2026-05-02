import sqlite3
import pathlib
import sys

# Resolve DB in apps/api
db = pathlib.Path(__file__).resolve().parents[1] / "battlecard.db"
run_id = '4e862bf4-defe-49b5-ba50-179c7d1efdd1'
pdf_path = 'generated_pdfs/StripePDFTest_4e862bf4-defe-49b5-ba50-179c7d1efdd1.pdf'

if not db.exists():
    print('DB not found:', db)
    sys.exit(2)

conn = sqlite3.connect(str(db))
cur = conn.cursor()
try:
    cur.execute('UPDATE runs SET pdf_path = ? WHERE id = ?', (pdf_path, run_id))
    conn.commit()
    cur.execute('SELECT id, pdf_path FROM runs WHERE id = ?', (run_id,))
    print('ROW:', cur.fetchone())
except Exception as e:
    print('ERROR', e)
finally:
    conn.close()
