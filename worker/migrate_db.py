"""
Migration script to add 'cancelled' status to existing database
"""

import sqlite3
from pathlib import Path

def migrate_database():
    db_path = Path("/app/data/bullseye.db")
    
    if not db_path.exists():
        print("Database not found")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Create new table with updated constraint
        cursor.execute("""
        CREATE TABLE jobs_new (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            repo_url TEXT NOT NULL,
            branch TEXT DEFAULT 'main',
            commit_hash TEXT,
            status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'cloning', 'detecting_components', 'scanning', 'analyzing', 'generating_report', 'completed', 'failed', 'cancelled')),
            status_message TEXT,
            progress INTEGER DEFAULT 0,
            progress_total INTEGER DEFAULT 100,
            progress_detail TEXT,
            model TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            error_message TEXT,
            config TEXT
        )
        """)
        
        # Copy data from old table
        cursor.execute("""
        INSERT INTO jobs_new 
        SELECT * FROM jobs
        """)
        
        # Drop old table and rename new one
        cursor.execute("DROP TABLE jobs")
        cursor.execute("ALTER TABLE jobs_new RENAME TO jobs")
        
        # Recreate indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC)")
        
        conn.commit()
        print("Database migrated successfully")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()
