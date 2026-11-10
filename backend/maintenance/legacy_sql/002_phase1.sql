-- Extensão histórica do esquema anterior; aplicada em ordem pelo comando adopt_legacy.
-- Compatibilidade: o banco novo usa manage.py migrate; estes scripts são utilizados por adopt_legacy.
-- MANTIS Fase 1: migração idempotente; não apaga registros.
CREATE TABLE IF NOT EXISTS sectors (
 id BIGSERIAL PRIMARY KEY,
 code VARCHAR(40) NOT NULL UNIQUE,
 name VARCHAR(120) NOT NULL,
 description TEXT,
 active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE lines ADD COLUMN IF NOT EXISTS sector_id BIGINT REFERENCES sectors(id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS idx_lines_sector ON lines(sector_id);
CREATE TABLE IF NOT EXISTS equipment_attachments (
 id BIGSERIAL PRIMARY KEY,
 equipment_id BIGINT NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
 kind VARCHAR(10) NOT NULL CHECK (kind IN ('PHOTO','MANUAL')),
 filename VARCHAR(180) NOT NULL,
 mime_type VARCHAR(60) NOT NULL,
 content BYTEA NOT NULL,
 size_bytes INTEGER NOT NULL CHECK(size_bytes > 0 AND size_bytes <= 5242880),
 uploaded_by BIGINT NOT NULL REFERENCES users(id),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(equipment_id, kind)
);
