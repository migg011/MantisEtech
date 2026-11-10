-- Cria ficha técnica, solicitações/itens de compra e eventos de aprovação no esquema legado.
-- Compatibilidade: o banco novo usa manage.py migrate; estes scripts são utilizados por adopt_legacy.
-- ETAPA 9 - ADITIVA. Execute somente após backup e revisão em ambiente de teste.
-- Depende da tabela spare_parts existente (EP19).
CREATE TABLE IF NOT EXISTS spare_part_technical (
 spare_part_id BIGINT PRIMARY KEY REFERENCES spare_parts(id) ON DELETE RESTRICT,
 description_en TEXT, ncm VARCHAR(10), pli_description TEXT, description_pt TEXT,
 classification TEXT, independent_function TEXT, connection_details TEXT,
 useful_life TEXT, asset_classification TEXT, main_function TEXT,
 secondary_function TEXT, raw_material TEXT, intended_use TEXT,
 application_machine TEXT, mechanical_electrical TEXT, current_type TEXT,
 power TEXT, voltage TEXT, amperage TEXT, picture_reference TEXT,
 fiscal_status VARCHAR(20) NOT NULL DEFAULT 'PENDENTE'
    CHECK(fiscal_status IN ('PENDENTE','EM_ANALISE','VALIDADA')),
 fiscal_validated_by BIGINT REFERENCES users(id), fiscal_validated_at TIMESTAMPTZ,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS spare_purchase_requests (
 id BIGSERIAL PRIMARY KEY,
 purchase_type VARCHAR(16) NOT NULL CHECK (purchase_type IN ('NACIONAL','IMPORTACAO')),
 status VARCHAR(24) NOT NULL DEFAULT 'RASCUNHO'
    CHECK(status IN ('RASCUNHO','EM_APROVACAO','DEVOLVIDA','REJEITADA','APROVADA')),
 requester_id BIGINT NOT NULL REFERENCES users(id), manager_id BIGINT NOT NULL REFERENCES users(id),
 work_order_id BIGINT REFERENCES work_orders(id),
 equipment_id BIGINT REFERENCES equipment(id),
 justification TEXT NOT NULL, priority VARCHAR(12) NOT NULL
    CHECK(priority IN ('BAIXA','MEDIA','ALTA','CRITICA')),
 manager_comment TEXT, submitted_at TIMESTAMPTZ, decided_at TIMESTAMPTZ,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS spare_purchase_request_items (
 id BIGSERIAL PRIMARY KEY,
 request_id BIGINT NOT NULL REFERENCES spare_purchase_requests(id) ON DELETE RESTRICT,
 spare_part_id BIGINT NOT NULL REFERENCES spare_parts(id) ON DELETE RESTRICT,
 quantity NUMERIC(14,3) NOT NULL CHECK(quantity > 0),
 item_note TEXT,
 -- fotografia do cadastro no momento da submissão evita alterações históricas
 technical_snapshot JSONB
);
CREATE INDEX IF NOT EXISTS idx_spare_purchase_requests_manager ON spare_purchase_requests(manager_id,status);
CREATE TABLE IF NOT EXISTS spare_purchase_events (
 id BIGSERIAL PRIMARY KEY, request_id BIGINT NOT NULL REFERENCES spare_purchase_requests(id),
 actor_id BIGINT NOT NULL REFERENCES users(id), action VARCHAR(32) NOT NULL,
 details TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS spare_purchase_notifications (
 id BIGSERIAL PRIMARY KEY, request_id BIGINT NOT NULL REFERENCES spare_purchase_requests(id),
 to_email TEXT NOT NULL, subject TEXT NOT NULL, body TEXT NOT NULL,
 state VARCHAR(24) NOT NULL DEFAULT 'PENDENTE'
    CHECK(state IN ('PENDENTE','ENVIADO','FALHOU')),
 attempts INT NOT NULL DEFAULT 0, error TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 sent_at TIMESTAMPTZ
);
