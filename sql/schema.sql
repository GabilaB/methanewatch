-- Next-stage persistent storage schema. MVP currently writes portable file products.
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE TABLE IF NOT EXISTS ingestion_runs (
  run_id BIGSERIAL PRIMARY KEY, provider TEXT NOT NULL, input_sha256 CHAR(64) NOT NULL,
  started_at TIMESTAMPTZ DEFAULT now(), accepted_rows INT, rejected_rows INT,
  UNIQUE(provider, input_sha256)
);
CREATE TABLE IF NOT EXISTS detections (
  provider TEXT NOT NULL, detection_id TEXT NOT NULL,
  observed_at TIMESTAMPTZ NOT NULL, geom GEOMETRY(Point,4326) NOT NULL,
  source_id TEXT, flux_tph DOUBLE PRECISION CHECK (flux_tph >= 0),
  input_sha256 CHAR(64) NOT NULL,
  PRIMARY KEY(provider, detection_id)
);
CREATE INDEX IF NOT EXISTS ix_detection_geom ON detections USING GIST(geom);
CREATE INDEX IF NOT EXISTS ix_detection_time ON detections(observed_at);
CREATE TABLE IF NOT EXISTS data_quality_issues (
  issue_id BIGSERIAL PRIMARY KEY, provider TEXT NOT NULL,
  detection_id TEXT, reason TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT now()
);
