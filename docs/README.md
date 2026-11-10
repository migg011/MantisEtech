# Documentação do Mantis

Os guias Markdown têm nomes e conteúdo em português. Os arquivos técnicos e
os diretórios mantêm os nomes em inglês. A interface permanece em PT-BR.

## Guias funcionais

- [Categorias de materiais](CATEGORIAS_PECAS.md)
- [Entradas e movimentações de estoque](ENTRADA_PECAS.md)
- [Ficha de peças](FICHA_PECAS.md)
- [Montagem de linhas SMT](MONTAGEM_LINHA_SMT.md)
- [Manutenção preventiva](MANUTENCAO_PREVENTIVA.md)
- [Ordens preventivas](ORDENS_PREVENTIVAS.md)
- [Painel operacional](PAINEL_OPERACIONAL.md)
- [Transferência de equipamentos](TRANSFERENCIA_EQUIPAMENTOS.md)
- [Proposta de reposição e compras](PROPOSTA_REPOSICAO_E_COMPRAS.md): proposta, não descrição de funcionalidade já implementada.

## Código e banco

- [Caminhos atuais do código](CODE_PATHS.json): substitui o mapa antigo que apontava para arquivos em português removidos.
- [Arquitetura atual](../backend/ESTRUTURA.md).
- `database/`: catálogos, consultas, diagramas e apresentações históricos.
  São retratos anteriores à refatoração e podem omitir tabelas ou alterações
  recentes. Para decisões sobre o esquema atual, consulte os modelos e migrações
  em `backend/maintenance`. Os identificadores físicos do banco continuam em PT-BR.
- `database/exports/`: versões exportadas preservadas para consulta.
- `database/schema-reference/er/`: diagramas e fontes editáveis preservados.

## Limpeza

Foram retirados de `docs` as fotos e experimentos visuais de equipamentos,
capturas antigas de testes, prévias de diagramas, ZIPs redundantes e mapas/guias
que descreviam a arquitetura em português já substituída. Os recursos usados
pelo aplicativo em `frontend/src/assets` foram preservados.

Uma cópia anterior à limpeza foi guardada fora do repositório, em
`../Mantis-docs-backup-2026-11-07` (relativo à raiz do projeto).
