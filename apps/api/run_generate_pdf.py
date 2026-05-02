import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.database import get_run, update_run
from app.services.pdf_export import generate_pdf

rid = 'c7475434-0f99-44ca-b59e-798482b285dd'
run = get_run(rid)
print('have markdown:', bool(run.get('markdown')))
try:
    path = generate_pdf(run.get('markdown',''), rid, run.get('competitor_name','battlecard'))
    print('generate_pdf returned:', path)
    if path:
        update_run(rid, pdf_path=path)
except Exception as e:
    import traceback
    traceback.print_exc()
