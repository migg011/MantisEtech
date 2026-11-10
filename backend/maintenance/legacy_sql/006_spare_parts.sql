-- Cria o cadastro mestre de peças e seus vínculos de compatibilidade com máquinas.
-- Compatibilidade: o banco novo usa manage.py migrate; estes scripts são utilizados por adopt_legacy.
-- EP19 MANTIS: cadastro mestre aditivo. Não altera estoques nem tabelas existentes.
CREATE TABLE IF NOT EXISTS spare_parts (
 id BIGSERIAL PRIMARY KEY,
 code VARCHAR(40) NOT NULL UNIQUE,
 description VARCHAR(250) NOT NULL,
 part_number VARCHAR(120), manufacturer VARCHAR(160),
 category VARCHAR(100), unit VARCHAR(20) NOT NULL DEFAULT 'UN',
 minimum_stock NUMERIC(14,3) NOT NULL DEFAULT 0 CHECK (minimum_stock >= 0),
 maximum_stock NUMERIC(14,3) CHECK (maximum_stock IS NULL OR maximum_stock >= minimum_stock),
 reorder_point NUMERIC(14,3) NOT NULL DEFAULT 0 CHECK (reorder_point >= 0),
 storage_location VARCHAR(160), preferred_supplier VARCHAR(160),
 average_cost NUMERIC(14,2) CHECK (average_cost IS NULL OR average_cost >= 0),
 last_cost NUMERIC(14,2) CHECK (last_cost IS NULL OR last_cost >= 0),
 photo_filename VARCHAR(255), photo_mime VARCHAR(100), photo_data BYTEA,
 datasheet_filename VARCHAR(255), datasheet_data BYTEA,
 active BOOLEAN NOT NULL DEFAULT true,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS spare_part_compatibility (
 spare_part_id BIGINT NOT NULL REFERENCES spare_parts(id) ON DELETE CASCADE,
 equipment_id BIGINT NOT NULL REFERENCES equipment(id) ON DELETE RESTRICT,
 PRIMARY KEY(spare_part_id,equipment_id)
);
CREATE INDEX IF NOT EXISTS idx_spare_parts_search ON spare_parts(active,description);
CREATE INDEX IF NOT EXISTS idx_spare_parts_part_number ON spare_parts(part_number);
