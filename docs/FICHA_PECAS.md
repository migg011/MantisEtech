# Ficha padronizada de peças

O Part Number identifica visualmente a peça. A descrição e o fabricante ajudam a distinguir itens; peças sem Part Number continuam consultáveis pela descrição. O ID e o código interno são preservados no banco para manter os vínculos existentes. O Part Number não se torna uma chave única, pois pode depender do fabricante.

## Onde consultar

- Spare Parts: clique no Part Number na listagem.
- Preventivas, aba Spare Parts: clique no Part Number nos resultados ou na lista de compra.
- OS, aba Peças: clique no Part Number ou em Solicitar peça. A seleção mostra a mesma ficha antes de informar quantidade e observação.
- Compras: pesquise por Part Number, descrição ou fabricante. A seleção apresenta a ficha; os itens de uma solicitação também têm Ver ficha da peça.

A ficha contém foto, dados gerais, referências de estoque/custos e dados técnicos. Os limites de estoque são referências, sem saldo ou baixa automática. As permissões existentes de manutenção são mantidas.

## Para aprendizagem

A apresentação é reutilizada por meio de PartSheet e PartQuery, em frontend/src/app/shared/part-sheet.component.ts e seus arquivos HTML/SCSS. Assim, um ajuste nessa ficha se reflete nas telas que a utilizam.

A consulta autenticada GET /api/spare-parts/:id/details fica em maintenance/api.py; a foto é baixada separadamente, sem incluir o binário nas listas. O catálogo aceita o parâmetro q para buscar por Part Number, descrição ou fabricante.

O CSV de compra inclui Part Number, descrição e fabricante. Novos envios para aprovação congelam esses dados junto da ficha técnica. A ficha de consulta mostra o cadastro atual; o CSV conserva o registro do envio. Compras antigas sem esses campos no retrato usam os dados atuais disponíveis.

Não há migração de banco nesta mudança. Testes de API usam um banco isolado; a prévia visual também utiliza dados simulados.

