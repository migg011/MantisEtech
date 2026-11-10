-- Esquema original: tabelas e restrições de usuários, linhas, equipamentos e ordens de serviço.
-- Compatibilidade: o banco novo usa manage.py migrate; estes scripts são utilizados por adopt_legacy.
CREATE TABLE IF NOT EXISTS lines (
 id BIGSERIAL PRIMARY KEY, code VARCHAR(40) NOT NULL UNIQUE, name VARCHAR(120) NOT NULL,
 description TEXT, active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS users (
 id BIGSERIAL PRIMARY KEY, name VARCHAR(160) NOT NULL, registration VARCHAR(50) NOT NULL UNIQUE,
 password_hash TEXT NOT NULL, role VARCHAR(20) NOT NULL CHECK(role IN ('ADMINISTRADOR','TECNICO','OPERADOR')),
 line_id BIGINT REFERENCES lines(id) ON DELETE RESTRICT, active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 CONSTRAINT operator_requires_line CHECK(role <> 'OPERADOR' OR line_id IS NOT NULL)
);
CREATE TABLE IF NOT EXISTS equipment_types (
 id SMALLINT PRIMARY KEY, name VARCHAR(100) NOT NULL UNIQUE
);
INSERT INTO equipment_types(id,name) VALUES
 (1,'PICK & PLACE'),(2,'PRINTER'),(3,'CONVEYOR'),(4,'BUFFER'),(5,'AOI'),(6,'SPI'),
 (7,'ROUTER'),(8,'LASER'),(9,'VACUUM LOADER'),(10,'MAGAZINE LOADER'),
 (11,'REFLOW'),(12,'DISPENSING') ON CONFLICT(id) DO NOTHING;
CREATE TABLE IF NOT EXISTS equipment (
 id BIGSERIAL PRIMARY KEY, equipment_type_id SMALLINT NOT NULL REFERENCES equipment_types(id),
 model_number VARCHAR(100), model VARCHAR(160), serial VARCHAR(160) UNIQUE, manufacturer VARCHAR(160),
 manufacturing_date DATE, length_mm NUMERIC(12,2), width_mm NUMERIC(12,2), height_mm NUMERIC(12,2),
 weight_kg NUMERIC(12,2), voltage_v NUMERIC(12,2), frequency_hz NUMERIC(12,2),
 current_a NUMERIC(12,2), power_w NUMERIC(12,2), pneumatic_pressure_bar NUMERIC(12,2),
 asset_number VARCHAR(100) UNIQUE, description TEXT, process_description TEXT,
 line_id BIGINT REFERENCES lines(id) ON DELETE SET NULL, position INTEGER CHECK(position > 0),
 active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 CONSTRAINT position_requires_line CHECK(position IS NULL OR line_id IS NOT NULL),
 CONSTRAINT line_requires_position CHECK(line_id IS NULL OR position IS NOT NULL),
 CONSTRAINT line_position_unique UNIQUE(line_id,position)
);
CREATE TABLE IF NOT EXISTS work_orders (
 id BIGSERIAL PRIMARY KEY, equipment_id BIGINT NOT NULL REFERENCES equipment(id),
 opened_by BIGINT NOT NULL REFERENCES users(id), assigned_to BIGINT REFERENCES users(id),
 priority VARCHAR(20) NOT NULL DEFAULT 'MEDIA' CHECK(priority IN ('BAIXA','MEDIA','ALTA','CRITICA')),
 status VARCHAR(20) NOT NULL DEFAULT 'ABERTA' CHECK(status IN ('ABERTA','EM_ANDAMENTO','CONCLUIDA')),
 problem TEXT NOT NULL CHECK(length(trim(problem)) >= 5), root_cause TEXT, corrective_action TEXT,
 preventive_action TEXT, started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_equipment_line ON equipment(line_id,position);
CREATE INDEX IF NOT EXISTS idx_orders_equipment ON work_orders(equipment_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_status ON work_orders(status);
-- Nenhum usuário, linha ou equipamento é pré-cadastrado neste script.
