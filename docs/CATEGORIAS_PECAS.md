# Categorias de materiais — Spare Parts

## Como usar

1. Na **Central de Cadastros**, o administrador abre o card **Categorias de materiais**.
2. Informa o nome e, se desejar, uma descrição. Há exemplos iniciais: NPM, NXT, Impressoras, Limpeza, Lubrificantes e EPI.
3. Ao cadastrar ou editar uma peça, marca uma ou mais categorias.
4. Na lista de peças, seleciona uma categoria para filtrar. A pesquisa por Part Number, descrição ou fabricante funciona junto desse filtro.
5. O relatório de inventário usa a mesma categoria e pesquisa, inclusive no CSV e na impressão.

## Regras

- A categoria classifica o material; não representa vínculo com uma máquina individual.
- A mesma peça pode pertencer a NPM e NXT sem duplicar o cadastro nem o estoque.
- Apenas administradores criam, renomeiam, desativam ou reativam categorias. Técnicos podem consultar e filtrar.
- Grafias diferentes apenas por maiúsculas, acentos ou espaços são consideradas o mesmo nome.
- Renomear preserva os vínculos. Desativar impede novas associações, preserva as existentes e permite pesquisas históricas.
- As categorias antigas escritas nas peças foram convertidas para este cadastro. Nenhuma categoria foi atribuída por suposição baseada no modelo ou no Part Number.
- O campo textual antigo permanece no banco para compatibilidade. A fonte usada na interface é a relação de categorias.

## Banco e código

- `CategoriaMaterial`: tabela `categorias_materiais`, nome, descrição, situação e chave normalizada única.
- Relação muitos-para-muitos `SparePart.categorias`: tabela `categorias_pecas`.
- Migração 0018 cria a estrutura; 0019 preserva classificações antigas e prepara os exemplos.
- API: `/api/part-categories` e `/api/part-categories/<id>`.
- Peças recebem `categoryIds`; lista omitida preserva vínculos, lista vazia remove os vínculos.
- Filtro de catálogo e inventário: `categoryId`.
- Testes: `maintenance/tests/test_categories.py`. A prévia visual usa somente dados simulados.

O cadastro de categorias já pode ser reutilizado numa próxima etapa de materiais de consumo e reposição automática. Esta entrega não altera o saldo nem cria compras automáticas.
