"""
Migration script to add review_complete column to audit_verifications table.
Run this after updating the models.py to add the new field.
"""

import sqlite3
import os

def migrate():
    """Add review_complete column to audit_verifications table."""
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'gdpr_audit.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if column already exists
    cursor.execute("PRAGMA table_info(audit_verifications)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'review_complete' in columns:
        print("Column 'review_complete' already exists in audit_verifications table")
        conn.close()
        return
    
    # Add the column
    try:
        cursor.execute("ALTER TABLE audit_verifications ADD COLUMN review_complete BOOLEAN DEFAULT 0 NOT NULL")
        conn.commit()
        print("✓ Successfully added 'review_complete' column to audit_verifications table")
    except Exception as e:
        print(f"Error adding column: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
