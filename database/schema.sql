-- Bull's Eye SQLite Schema
-- Lightweight database for codebase analysis

-- Jobs table - main analysis jobs
CREATE TABLE IF NOT EXISTS jobs (
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
    celery_task_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    config TEXT  -- JSON config
);

-- Components table - detected code components
CREATE TABLE IF NOT EXISTS components (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    component_type TEXT,  -- 'module', 'package', 'service', 'library', etc.
    language TEXT,
    file_count INTEGER DEFAULT 0,
    line_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'scanning', 'analyzing', 'completed', 'failed')),
    analysis_summary TEXT,
    health_score INTEGER,  -- 0-100
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Files table - individual files in components  
CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY,
    component_id TEXT NOT NULL REFERENCES components(id) ON DELETE CASCADE,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    language TEXT,
    line_count INTEGER DEFAULT 0,
    size_bytes INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'analyzed', 'skipped', 'error')),
    analysis_summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Findings table - all issues found
CREATE TABLE IF NOT EXISTS findings (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    component_id TEXT REFERENCES components(id) ON DELETE CASCADE,
    file_id TEXT REFERENCES files(id) ON DELETE CASCADE,
    scanner TEXT NOT NULL,  -- 'gitleaks', 'semgrep', 'llm', etc.
    rule_id TEXT,
    severity TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),
    category TEXT,  -- 'security', 'quality', 'performance', 'style', etc.
    title TEXT NOT NULL,
    description TEXT,
    file_path TEXT,
    line_start INTEGER,
    line_end INTEGER,
    code_snippet TEXT,
    suggestion TEXT,
    llm_explanation TEXT,
    fingerprint TEXT,  -- For deduplication
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(job_id, fingerprint)
);

-- Scanner results - raw output from each scanner
CREATE TABLE IF NOT EXISTS scanner_results (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    component_id TEXT REFERENCES components(id) ON DELETE CASCADE,
    scanner TEXT NOT NULL,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    findings_count INTEGER DEFAULT 0,
    raw_output TEXT,
    error_message TEXT
);

-- Status updates - detailed progress tracking
CREATE TABLE IF NOT EXISTS status_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    stage TEXT NOT NULL,
    message TEXT NOT NULL,
    progress INTEGER,
    details TEXT  -- JSON with extra info
);

-- Reports table - generated reports
CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    report_type TEXT DEFAULT 'full',
    format TEXT DEFAULT 'json',
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_components_job ON components(job_id);
CREATE INDEX IF NOT EXISTS idx_files_component ON files(component_id);
CREATE INDEX IF NOT EXISTS idx_files_job ON files(job_id);
CREATE INDEX IF NOT EXISTS idx_findings_job ON findings(job_id);
CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(severity);
CREATE INDEX IF NOT EXISTS idx_findings_scanner ON findings(scanner);
CREATE INDEX IF NOT EXISTS idx_status_updates_job ON status_updates(job_id);
CREATE INDEX IF NOT EXISTS idx_scanner_results_job ON scanner_results(job_id);
