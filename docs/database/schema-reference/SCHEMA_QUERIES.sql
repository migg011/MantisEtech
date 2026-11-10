-- Consultas de leitura: execute no pgAdmin ou DBeaver conectado ao MANTIS.
-- O limite evita carregar todos os equipamentos de uma vez.
SELECT id, nome, matricula, perfil, ativo FROM usuarios ORDER BY nome LIMIT 50;
SELECT e.id, e.nome, e.numero_serie, s.nome AS setor
FROM equipamentos e LEFT JOIN setores s ON s.id = e.setor_id
ORDER BY e.id LIMIT 50;
SELECT codigo, descricao, numero_peca, fabricante FROM pecas_reposicao ORDER BY descricao LIMIT 50;
