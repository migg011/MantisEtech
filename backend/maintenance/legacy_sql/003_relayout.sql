-- Evolução do layout e histórico de alocação das máquinas no sistema anterior.
-- Compatibilidade: o banco novo usa manage.py migrate; estes scripts são utilizados por adopt_legacy.
-- Fase 2: histórico de alocação; migração aditiva e idempotente.
-- Nenhum equipamento, linha, OS ou anexo é apagado.
CREATE TABLE IF NOT EXISTS equipment_movements (
 id BIGSERIAL PRIMARY KEY,
 equipment_id BIGINT NOT NULL REFERENCES equipment(id) ON DELETE RESTRICT,
 from_line_id BIGINT REFERENCES lines(id) ON DELETE RESTRICT,
 from_position INTEGER,
 to_line_id BIGINT REFERENCES lines(id) ON DELETE RESTRICT,
 to_position INTEGER,
 action VARCHAR(20) NOT NULL CHECK(action IN ('ALOCACAO','REMOCAO','DESMONTAGEM')),
 performed_by BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_equipment_movements_equipment ON equipment_movements(equipment_id,created_at DESC);
