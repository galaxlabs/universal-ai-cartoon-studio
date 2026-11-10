PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = FULL;
PRAGMA busy_timeout = 5000;

CREATE TABLE projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL,
  root_path TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE series (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), name TEXT NOT NULL, premise TEXT, status TEXT NOT NULL, UNIQUE(project_id,name));
CREATE TABLE episodes (id TEXT PRIMARY KEY, series_id TEXT NOT NULL REFERENCES series(id), code TEXT NOT NULL, title TEXT NOT NULL, status TEXT NOT NULL, UNIQUE(series_id,code));
CREATE TABLE scenes (id TEXT PRIMARY KEY, episode_id TEXT NOT NULL REFERENCES episodes(id), code TEXT NOT NULL, title TEXT, status TEXT NOT NULL, UNIQUE(episode_id,code));
CREATE TABLE shots (id TEXT PRIMARY KEY, scene_id TEXT NOT NULL REFERENCES scenes(id), code TEXT NOT NULL, frame_start INTEGER, frame_end INTEGER, fps REAL, status TEXT NOT NULL, UNIQUE(scene_id,code));

CREATE TABLE characters (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), code TEXT NOT NULL, name TEXT NOT NULL, bible_status TEXT NOT NULL, UNIQUE(project_id,code));
CREATE TABLE assets (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), code TEXT NOT NULL, name TEXT NOT NULL, asset_type TEXT NOT NULL, lifecycle_state TEXT NOT NULL, protected INTEGER NOT NULL DEFAULT 0 CHECK(protected IN (0,1)), UNIQUE(project_id,code));
CREATE TABLE asset_versions (id TEXT PRIMARY KEY, asset_id TEXT NOT NULL REFERENCES assets(id), version INTEGER NOT NULL, status TEXT NOT NULL, workspace_path TEXT, sha256 TEXT, created_at TEXT NOT NULL, UNIQUE(asset_id,version));
CREATE TABLE character_versions (id TEXT PRIMARY KEY, character_id TEXT NOT NULL REFERENCES characters(id), asset_version_id TEXT REFERENCES asset_versions(id), version INTEGER NOT NULL, proportions_json TEXT, rig_signature TEXT, approved INTEGER NOT NULL DEFAULT 0 CHECK(approved IN (0,1)), UNIQUE(character_id,version));
CREATE TABLE files (id TEXT PRIMARY KEY, asset_version_id TEXT REFERENCES asset_versions(id), path TEXT NOT NULL UNIQUE, sha256 TEXT NOT NULL, size_bytes INTEGER NOT NULL, media_type TEXT, storage_zone TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE dependencies (id TEXT PRIMARY KEY, source_kind TEXT NOT NULL, source_id TEXT NOT NULL, target_kind TEXT NOT NULL, target_id TEXT NOT NULL, relation TEXT NOT NULL, UNIQUE(source_kind,source_id,target_kind,target_id,relation));

CREATE TABLE agents (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, role TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)), config_json TEXT);
CREATE TABLE mcp_servers (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, source_url TEXT, version TEXT, license TEXT, bind_host TEXT, permissions_json TEXT, status TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)));
CREATE TABLE skills (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, source TEXT, version TEXT, permissions_json TEXT, status TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)));
CREATE TABLE capabilities (id TEXT PRIMARY KEY, provider_kind TEXT NOT NULL, provider_id TEXT NOT NULL, capability TEXT NOT NULL, write_scope TEXT, approval_required INTEGER NOT NULL DEFAULT 1 CHECK(approval_required IN (0,1)), enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)), UNIQUE(provider_kind,provider_id,capability));

CREATE TABLE production_jobs (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), job_type TEXT NOT NULL, status TEXT NOT NULL, target_application TEXT, workspace_path TEXT NOT NULL, requested_by TEXT NOT NULL, approved_by TEXT, created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT, error_code TEXT);
CREATE TABLE job_events (id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL REFERENCES production_jobs(id), sequence INTEGER NOT NULL, event_type TEXT NOT NULL, payload_json TEXT, created_at TEXT NOT NULL, UNIQUE(job_id,sequence));
CREATE TABLE validation_reports (id TEXT PRIMARY KEY, job_id TEXT REFERENCES production_jobs(id), asset_version_id TEXT REFERENCES asset_versions(id), validator TEXT NOT NULL, status TEXT NOT NULL, report_path TEXT NOT NULL, report_sha256 TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE approvals (id TEXT PRIMARY KEY, subject_kind TEXT NOT NULL, subject_id TEXT NOT NULL, decision TEXT NOT NULL, decided_by TEXT NOT NULL, notes TEXT, evidence_json TEXT, created_at TEXT NOT NULL);
CREATE TABLE change_requests (id TEXT PRIMARY KEY, subject_kind TEXT NOT NULL, subject_id TEXT NOT NULL, requested_by TEXT NOT NULL, description TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, resolved_at TEXT);
CREATE TABLE backups (id TEXT PRIMARY KEY, subject_kind TEXT NOT NULL, subject_id TEXT NOT NULL, path TEXT NOT NULL, sha256 TEXT NOT NULL, restore_tested INTEGER NOT NULL DEFAULT 0 CHECK(restore_tested IN (0,1)), created_at TEXT NOT NULL);
CREATE TABLE components (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, source TEXT, version TEXT, license TEXT, status TEXT NOT NULL, permissions_json TEXT, test_result TEXT, risk TEXT, updated_at TEXT NOT NULL);
CREATE TABLE audit_events (id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT NOT NULL, action TEXT NOT NULL, subject_kind TEXT NOT NULL, subject_id TEXT NOT NULL, before_json TEXT, after_json TEXT, created_at TEXT NOT NULL);

CREATE INDEX idx_assets_project_type ON assets(project_id,asset_type);
CREATE INDEX idx_versions_asset_status ON asset_versions(asset_id,status);
CREATE INDEX idx_jobs_status_created ON production_jobs(status,created_at);
CREATE INDEX idx_events_job_sequence ON job_events(job_id,sequence);
CREATE INDEX idx_approvals_subject ON approvals(subject_kind,subject_id,created_at);
