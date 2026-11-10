-- Introduz a organização de linhas e equipamentos por setor no esquema legado.
-- Compatibilidade: o banco novo usa manage.py migrate; estes scripts são utilizados por adopt_legacy.
-- Setor proprietário permanente do equipamento; migração aditiva sem remoção de dados.
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS sector_id BIGINT REFERENCES sectors(id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS idx_equipment_sector ON equipment(sector_id,line_id);
-- Equipamentos preexistentes sem setor continuam sem atribuição até revisão administrativa.
