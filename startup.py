"""
Startup script: creates DB tables and runs initial data import if needed.
Safe to run on every deploy — skips anything already present.
"""
import os
import sys

sys.path.insert(0, '/app')

from flask import Flask
from config import config
from models import db, Domain, GDPRChecklist
import import_data as imp

app = Flask(__name__)
app.config.from_object(config[os.environ.get('FLASK_CONFIG', 'production')])
db.init_app(app)

with app.app_context():
    print("==> Running data import checks...")

    checklist_count = GDPRChecklist.query.count()
    domain_count = Domain.query.count()

    # Import checklist only if not already there
    if checklist_count == 0:
        imp.import_gdpr_checklist(os.path.join('/app', 'gdpr_checklist.json'))
    else:
        print(f"==> Checklist already present ({checklist_count} items) — skipping.")

    # Import domains — skips existing ones, so safe to run when partially complete
    total_before = Domain.query.count()
    mapping = imp.import_privacy_results(
        os.path.join('/app', 'privacy_results.csv'),
        os.path.join('/app', 'privacy')
    )
    imp.import_compliance_results(
        os.path.join('/app', 'compliance_results.csv'),
        mapping
    )
    total_after = Domain.query.count()
    if total_after == total_before:
        print(f"==> Domains already complete ({total_before}) — skipping.")

    # Back-fill any missing compliance labels (from partial failed imports)
    imp.update_compliance_labels(os.path.join('/app', 'compliance_results.csv'))

    # Create admin only if not already there
    imp.create_admin_user()

    print("==> Startup checks complete.")
