"""
Import existing GDPR compliance data into the database.
Run this script after setting up the database to import all existing data.
"""

import csv
import json
import os
import sys
from pathlib import Path

# Add parent directory to path to import config and models
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask
from config import config
from models import db, User, GDPRChecklist, Domain, QuestionAnswer

def import_gdpr_checklist(checklist_path):
    """Import GDPR checklist from JSON file."""
    print(f"Importing GDPR checklist from {checklist_path}...")
    
    with open(checklist_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    count = 0
    skipped = 0
    for item in data['checklist']:
        if GDPRChecklist.query.filter_by(question_id=item['id']).first():
            skipped += 1
            continue
        checklist_item = GDPRChecklist(
            question_id=item['id'],
            category=item['category'],
            section=item['section'],
            question_text=item['question'],
            gdpr_reference=item['gdpr_reference']
        )
        db.session.add(checklist_item)
        count += 1

    db.session.commit()
    print(f"✓ Imported {count} GDPR checklist items (skipped {skipped} existing)")

def import_privacy_results(csv_path, privacy_dir):
    """Import privacy results to build a mapping of domain -> URL and file path."""
    print(f"Importing privacy results from {csv_path}...")
    
    privacy_mapping = {}
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            domain = row['domain']
            privacy_file = os.path.join(privacy_dir, f"{domain}.txt")
            
            privacy_mapping[domain] = {
                'url': row['url'] if row['url'] else None,
                'source': row['source'] if row['source'] else None,
                'file_path': privacy_file if os.path.exists(privacy_file) else None
            }
    
    print(f"✓ Built privacy mapping for {len(privacy_mapping)} domains")
    return privacy_mapping

def import_compliance_results(csv_path, privacy_mapping):
    """Import compliance results using bulk inserts with ON CONFLICT DO NOTHING."""
    print(f"Importing compliance results from {csv_path}...")

    from sqlalchemy.dialects.postgresql import insert as pg_insert

    # Get all question IDs
    question_ids = {item.question_id for item in GDPRChecklist.query.all()}

    # ── Pass 1: read entire CSV into memory ───────────────────────────────
    domain_rows = []
    domain_qa_map = {}

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            domain = row['domain']
            privacy_info = privacy_mapping.get(domain, {})

            domain_rows.append({
                'domain':                domain,
                'compliance_label':      row.get('compliance_label') or None,
                'compliance_score':      int(row['compliance_score']) if row.get('compliance_score') else None,
                'language_detected':     row.get('language_detected') or None,
                'summary':               row.get('summary') or None,
                'translation_performed': row.get('translation_performed', '').lower() == 'true',
                'status':                row.get('status') or None,
                'error':                 row.get('error') or None,
                'privacy_url':           privacy_info.get('url'),
                'privacy_source':        privacy_info.get('source'),
                'privacy_file_path':     privacy_info.get('file_path'),
            })

            qas = []
            for qid in question_ids:
                answer_key   = f'q_{qid}_answer'
                evidence_key = f'q_{qid}_evidence'
                if answer_key in row:
                    qas.append({
                        'question_id': qid,
                        'ai_answer':   row.get(answer_key),
                        'ai_evidence': row.get(evidence_key),
                    })
            domain_qa_map[domain] = qas

    print(f"  {len(domain_rows)} rows in CSV — bulk inserting (duplicates skipped by DB)...")

    # ── Pass 2: bulk upsert domains — ON CONFLICT DO NOTHING ─────────────
    BATCH = 1000
    for i in range(0, len(domain_rows), BATCH):
        batch = domain_rows[i:i + BATCH]
        stmt = pg_insert(Domain.__table__).values(batch)
        stmt = stmt.on_conflict_do_nothing(index_elements=['domain'])
        db.session.execute(stmt)
        db.session.commit()
        print(f"  Domains: {min(i + BATCH, len(domain_rows))}/{len(domain_rows)}")

    # ── Pass 3: fetch IDs for ALL domains (new + pre-existing) ───────────
    all_names = [r['domain'] for r in domain_rows]
    id_map = {
        d.domain: d.id
        for d in db.session.query(Domain.id, Domain.domain)
                            .filter(Domain.domain.in_(all_names)).all()
    }

    # ── Pass 4: bulk insert QAs — skip domains that already have all answers ─
    # A domain is "complete" if it has answers for all 25 checklist questions
    expected_answer_count = len(question_ids)
    from sqlalchemy import func
    complete_domain_ids = {
        r[0] for r in db.session.query(QuestionAnswer.domain_id)
                                 .group_by(QuestionAnswer.domain_id)
                                 .having(func.count(QuestionAnswer.id) >= expected_answer_count)
                                 .all()
    }

    qa_rows = []
    for domain_name, qas in domain_qa_map.items():
        domain_id = id_map.get(domain_name)
        if not domain_id or domain_id in complete_domain_ids:
            continue
        # Delete any partial answers for this domain before re-inserting
        db.session.query(QuestionAnswer).filter_by(domain_id=domain_id).delete()
        for qa in qas:
            qa_rows.append({
                'domain_id':   domain_id,
                'question_id': qa['question_id'],
                'ai_answer':   qa['ai_answer'],
                'ai_evidence': qa['ai_evidence'],
            })

    print(f"  Inserting {len(qa_rows)} question answers in bulk...")
    if qa_rows:
        db.session.commit()  # flush the deletes first
    for i in range(0, len(qa_rows), BATCH):
        db.session.bulk_insert_mappings(QuestionAnswer, qa_rows[i:i + BATCH])
        db.session.commit()
        print(f"  Answers: {min(i + BATCH, len(qa_rows))}/{len(qa_rows)}")

    print(f"✓ Import complete — {len(domain_rows)} domains processed, {len(qa_rows)} answers inserted")

def update_compliance_labels(csv_path):
    """Back-fill compliance_label and compliance_score for domains missing them."""
    print("Checking for domains with missing compliance labels...")

    # Check for both NULL and empty string
    from sqlalchemy import or_
    null_count = db.session.query(Domain).filter(
        or_(Domain.compliance_label.is_(None), Domain.compliance_label == '')
    ).count()

    if null_count == 0:
        print("✓ All domains have compliance labels — nothing to update.")
        return

    print(f"  Found {null_count} domains with missing labels — back-filling from CSV...")

    updates = {}
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            label = row.get('compliance_label') or None
            if label:
                updates[row['domain']] = {
                    'compliance_label': label,
                    'compliance_score': int(row['compliance_score']) if row.get('compliance_score') else None,
                    'summary':          row.get('summary') or None,
                    'language_detected': row.get('language_detected') or None,
                }

    count = 0
    BATCH = 500
    domain_names = list(updates.keys())
    for i in range(0, len(domain_names), BATCH):
        batch_names = domain_names[i:i + BATCH]
        domains = db.session.query(Domain).filter(
            Domain.domain.in_(batch_names),
            or_(Domain.compliance_label.is_(None), Domain.compliance_label == '')
        ).all()
        for d in domains:
            data = updates.get(d.domain)
            if data:
                d.compliance_label  = data['compliance_label']
                d.compliance_score  = data['compliance_score']
                d.summary           = data['summary']
                d.language_detected = data['language_detected']
                count += 1
        db.session.commit()

    print(f"✓ Updated {count} domains with compliance labels.")


def create_admin_user():
    """Create initial admin user using credentials from environment variables."""
    print("Creating initial admin user...")

    admin = User.query.filter_by(username='admin').first()
    if admin:
        print("  Admin user already exists, skipping.")
        return

    admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
    admin_password = os.environ.get('ADMIN_PASSWORD')

    if not admin_password:
        raise ValueError(
            "\n[ERROR] ADMIN_PASSWORD environment variable is not set.\n"
            "Set it in your .env file before running the import script.\n"
            "Example: ADMIN_PASSWORD=your-strong-password-here"
        )

    admin = User(username=admin_username, role='admin', is_active=True)
    admin.set_password(admin_password)
    db.session.add(admin)
    db.session.commit()

    print(f"✓ Created admin user (username: {admin_username})")
    print("  Password was read from ADMIN_PASSWORD environment variable.")

def main():
    """Main import function."""
    # Determine paths — data files live alongside this script
    script_dir = os.path.dirname(os.path.abspath(__file__))

    checklist_path = os.path.join(script_dir, 'gdpr_checklist.json')
    compliance_csv = os.path.join(script_dir, 'compliance_results.csv')
    privacy_csv = os.path.join(script_dir, 'privacy_results.csv')
    privacy_dir = os.path.join(script_dir, 'privacy')
    
    # Verify files exist
    if not os.path.exists(checklist_path):
        print(f"Error: Checklist file not found: {checklist_path}")
        return
    
    if not os.path.exists(compliance_csv):
        print(f"Error: Compliance CSV not found: {compliance_csv}")
        return
    
    if not os.path.exists(privacy_csv):
        print(f"Error: Privacy CSV not found: {privacy_csv}")
        return
    
    if not os.path.exists(privacy_dir):
        print(f"Error: Privacy directory not found: {privacy_dir}")
        return
    
    # Create Flask app — use FLASK_CONFIG env var, default to development
    app = Flask(__name__)
    config_name = os.environ.get('FLASK_CONFIG', 'development')
    app.config.from_object(config[config_name])
    
    # Initialize database
    db.init_app(app)
    
    with app.app_context():
        # Create all tables
        db.create_all()
        print("✓ Database tables created")
        
        # Import data
        import_gdpr_checklist(checklist_path)
        privacy_mapping = import_privacy_results(privacy_csv, privacy_dir)
        import_compliance_results(compliance_csv, privacy_mapping)
        create_admin_user()
        
        print("\n✓ Data import completed successfully!")

if __name__ == '__main__':
    main()
