-- MANTIS: consultas para explicar o modelo no pgAdmin ou DataGrip.
-- Somente leitura. Execute no banco mantis_django correspondente ao projeto.
-- Os resultados são dados reais do ambiente consultado; revise-os antes de projetar.
BEGIN TRANSACTION READ ONLY;
SET LOCAL TIME ZONE 'America/Manaus';

-- 1. Identifica o ambiente sem mostrar credenciais.
SELECT current_database() AS banco, current_setting('server_version') AS versao_postgres,
       current_schema() AS esquema;

-- 2. Inventário físico: uma linha por tabela, sem consultar registros pessoais.
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
ORDER BY table_name;

-- 3. Dicionário completo de colunas e nulabilidade.
SELECT table_name, ordinal_position, column_name, data_type, is_nullable, column_default
FROM information_schema.columns WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;

-- 4. Regras efetivamente instaladas: PK, FK, UNIQUE e CHECK.
SELECT t.relname AS tabela, c.conname AS restricao, c.contype AS tipo,
       pg_get_constraintdef(c.oid) AS definicao
FROM pg_constraint c
JOIN pg_class t ON t.oid = c.conrelid
JOIN pg_namespace n ON n.oid = t.relnamespace
WHERE n.nspname = 'public' ORDER BY t.relname, c.contype, c.conname;

-- 5. Mapa físico: máquina → tipo → setor → linha.
-- As duas localizações são opcionais no esquema; por isso LEFT JOIN.
SELECT e.id, e.name AS equipamento, e.asset_number AS patrimonio,
       t.name AS tipo, s.name AS setor, l.name AS linha, e.position AS posicao
FROM equipment e
JOIN equipment_types t ON t.id = e.equipment_type_id
LEFT JOIN sectors s ON s.id = e.sector_id
LEFT JOIN lines l ON l.id = e.line_id
WHERE e.active ORDER BY s.name, l.name, e.position, e.id;

-- 6. Indicador agregado de OS corretivas; não soma tempos de paradas sobrepostas da linha.
SELECT status, count(*) AS quantidade,
       round(avg(downtime_seconds) / 60.0, 2) AS media_minutos_os_encerradas
FROM work_orders GROUP BY status ORDER BY status;

-- 7. Próximos vencimentos reais. O modelo JSON de 2026 não aparece nesta consulta.
SELECT p.id AS agenda_id, e.name AS equipamento, p.frequency,
       p.next_due, p.last_performed,
       CASE WHEN p.next_due < CURRENT_DATE THEN 'VENCIDA'
            WHEN p.next_due = CURRENT_DATE THEN 'HOJE' ELSE 'EM_DIA' END AS situacao
FROM equipment_preventives p JOIN equipment e ON e.id = p.equipment_id
WHERE p.active AND e.active ORDER BY p.next_due, e.name;

-- 8. OS preventiva → agenda → máquina. Não existe equipment_id direto em preventive_orders.
SELECT o.id, 'PREV-' || lpad(o.id::text, greatest(6, length(o.id::text)), '0') AS numero_exibido,
       o.status, o.planned_date, p.equipment_id,
       o.equipment_snapshot ->> 'name' AS nome_preservado,
       e.name AS nome_atual, o.revision
FROM preventive_orders o
JOIN equipment_preventives p ON p.id = o.schedule_id
JOIN equipment e ON e.id = p.equipment_id
ORDER BY o.planned_date, o.id;

-- 9. Compras com vários itens, inclusive as que não têm máquina ou OS vinculada.
SELECT r.id, r.status, r.purchase_type,
       count(i.id) AS itens, r.equipment_id, r.work_order_id
FROM spare_purchase_requests r
LEFT JOIN spare_purchase_request_items i ON i.request_id = r.id
GROUP BY r.id ORDER BY r.id;

-- 10. A ficha atual e a cópia congelada são conceitos diferentes.
-- A presença do snapshot indica gravação de uma cópia; não implica aprovação do gestor.
SELECT i.id AS item_id, i.request_id, i.spare_part_id, i.quantity,
       (i.technical_snapshot IS NOT NULL) AS possui_copia_tecnica,
       t.fiscal_status AS validacao_da_ficha_atual
FROM spare_purchase_request_items i
LEFT JOIN spare_part_technical t ON t.spare_part_id = i.spare_part_id
ORDER BY i.request_id, i.id;

-- 11. Integridade da preventiva: o índice parcial deve permitir só uma OS ABERTA por agenda.
SELECT indexname, indexdef FROM pg_indexes
WHERE schemaname = 'public' AND tablename = 'preventive_orders'
ORDER BY indexname;

-- 12. As migrações são o histórico de evolução do esquema, não um log de edição de registros.
SELECT app, name, applied FROM django_migrations ORDER BY applied, app, name;

COMMIT;
