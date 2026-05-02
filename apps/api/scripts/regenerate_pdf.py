import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.database import get_run, update_run
from app.services.pdf_export import generate_pdf

if len(sys.argv) < 2:
    print("Usage: python regenerate_pdf.py <run_id>")
    sys.exit(1)

run_id = sys.argv[1]
run = get_run(run_id)
if run is None:
    print(f"Run not found: {run_id}")
    sys.exit(2)

markdown = run.get("markdown")
competitor = run.get("competitor_name") or "battlecard"
if not markdown:
    print("No markdown available for run; cannot generate PDF.")
    sys.exit(3)

print(f"Generating PDF for run {run_id} ({competitor})...")
pdf_path = generate_pdf(markdown, run_id, competitor)
if pdf_path:
    update_run(run_id, pdf_path=pdf_path)
    print(f"PDF generated: {pdf_path}")
    sys.exit(0)
else:
    print("PDF generation failed")
    sys.exit(4)
