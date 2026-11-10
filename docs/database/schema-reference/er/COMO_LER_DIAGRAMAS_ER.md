# ER MANTIS — guia de leitura

Base: catálogo PostgreSQL de 2026-10-30T20:18:45.567971-04:00.

Entidade é uma tabela; atributo é uma coluna; relacionamento é uma referência (FK) entre tabelas.
PK identifica o registro. FK guarda a chave de outro registro. 1 = exatamente um; 0..1 = opcional, no máximo um; 0..N = zero ou vários.
Os números ao lado de cada entidade indicam quantos registros daquele lado podem participar para um registro do outro lado.
As figuras exibem campos e ligações principais. O catálogo completo conserva todos os vínculos e todas as colunas.

## Todas as entidades — 21

Aqui estão todas as 21 entidades de negócio, incluindo usuários, documentos, movimentações, roteiros, execuções, pendências e compras. As conexões são detalhadas nas páginas por área.

Esta página é o índice visual completo: esquerda = estrutura, acesso e histórico; centro = manutenção; direita = peças e compras. Para seguir as linhas de relacionamento, escolha a página da área. As cinco tabelas internas do Django têm uma página própria.


## Comece por aqui

O equipamento é o ponto central. A preventiva segue uma programação; a corretiva nasce de um problema. São ordens em tabelas diferentes.

Exemplo ilustrativo: uma máquina cadastrada pode ter uma agenda mensal. A cada ciclo pode ser emitida uma OS preventiva. Uma falha nessa mesma máquina pode originar uma OS corretiva.

- R21: Cada registro de Linhas de produção aponta para zero ou um registro de Setores. Cada registro de Setores pode ser referenciado por zero, um ou vários registros de Linhas de produção. FK: `linhas.setor_id`.
- R09: Cada registro de Equipamentos aponta para zero ou um registro de Linhas de produção. Cada registro de Linhas de produção pode ser referenciado por zero, um ou vários registros de Equipamentos. FK: `equipamentos.linha_id`.
- R11: Cada registro de Equipamentos aponta para exatamente um registro de Tipos de equipamento. Cada registro de Tipos de equipamento pode ser referenciado por zero, um ou vários registros de Equipamentos. FK: `equipamentos.tipo_equipamento_id`.
- R01: Cada registro de Programação preventiva aponta para exatamente um registro de Equipamentos. Cada registro de Equipamentos pode ser referenciado por zero, um ou vários registros de Programação preventiva. FK: `agendas_preventiva.equipamento_id`.
- R31: Cada registro de OS corretivas aponta para exatamente um registro de Equipamentos. Cada registro de Equipamentos pode ser referenciado por zero, um ou vários registros de OS corretivas. FK: `ordens_servico.equipamento_id`.
- R26: Cada registro de OS preventivas aponta para exatamente um registro de Programação preventiva. Cada registro de Programação preventiva pode ser referenciado por zero, um ou vários registros de OS preventivas. FK: `ordens_preventiva.agenda_id`.

## Estrutura industrial

Primeiro cadastre o setor e o tipo; depois, o equipamento. A linha organiza a alocação atual da máquina.

A máquina pode estar sem linha e sem posição, disponível no repositório. Setor proprietário e linha de alocação são informações diferentes. O banco permite alguns vínculos vazios que o formulário pode exigir no cadastro.

- R21: Cada registro de Linhas de produção aponta para zero ou um registro de Setores. Cada registro de Setores pode ser referenciado por zero, um ou vários registros de Linhas de produção. FK: `linhas.setor_id`.
- R09: Cada registro de Equipamentos aponta para zero ou um registro de Linhas de produção. Cada registro de Linhas de produção pode ser referenciado por zero, um ou vários registros de Equipamentos. FK: `equipamentos.linha_id`.
- R11: Cada registro de Equipamentos aponta para exatamente um registro de Tipos de equipamento. Cada registro de Tipos de equipamento pode ser referenciado por zero, um ou vários registros de Equipamentos. FK: `equipamentos.tipo_equipamento_id`.
- R10: Cada registro de Equipamentos aponta para zero ou um registro de Setores. Cada registro de Setores pode ser referenciado por zero, um ou vários registros de Equipamentos. FK: `equipamentos.setor_id`.

## Manutenção preventiva

O roteiro pertence ao tipo de equipamento. A agenda pertence à máquina. A OS preserva o que foi emitido; a execução registra o que foi concluído.

Uma agenda pode ter várias OS ao longo do tempo, mas o banco permite somente uma ABERTA por agenda. Cada OS pode ter zero ou uma execução. O roteiro é herdado pela aplicação: não há FK direta da agenda para o roteiro. O calendário provisório de 2026 é um arquivo JSON, fora destas tabelas.

- R11: Cada registro de Equipamentos aponta para exatamente um registro de Tipos de equipamento. Cada registro de Tipos de equipamento pode ser referenciado por zero, um ou vários registros de Equipamentos. FK: `equipamentos.tipo_equipamento_id`.
- R39: Cada registro de Roteiros de preventiva aponta para exatamente um registro de Tipos de equipamento. Cada registro de Tipos de equipamento pode ser referenciado por zero, um ou vários registros de Roteiros de preventiva. FK: `roteiros_preventiva.tipo_equipamento_id`.
- R01: Cada registro de Programação preventiva aponta para exatamente um registro de Equipamentos. Cada registro de Equipamentos pode ser referenciado por zero, um ou vários registros de Programação preventiva. FK: `agendas_preventiva.equipamento_id`.
- R26: Cada registro de OS preventivas aponta para exatamente um registro de Programação preventiva. Cada registro de Programação preventiva pode ser referenciado por zero, um ou vários registros de OS preventivas. FK: `ordens_preventiva.agenda_id`.
- R14: Cada registro de Execuções preventivas aponta para exatamente um registro de Programação preventiva. Cada registro de Programação preventiva pode ser referenciado por zero, um ou vários registros de Execuções preventivas. FK: `execucoes_preventiva.agenda_id`.
- R15: Cada registro de Execuções preventivas aponta para zero ou um registro de OS preventivas. Cada registro de OS preventivas pode ser referenciado por zero ou um registro de Execuções preventivas. FK: `execucoes_preventiva.ordem_preventiva_id`.

## Manutenção corretiva

A OS registra a falha da máquina. Ela pode gerar pendências e solicitações diretas de peças, sem criar uma compra automaticamente.

Concluir a OS não resolve suas pendências automaticamente. Solicitar uma peça para manutenção não significa registrar uma retirada de estoque nem abrir uma solicitação de compra.

- R31: Cada registro de OS corretivas aponta para exatamente um registro de Equipamentos. Cada registro de Equipamentos pode ser referenciado por zero, um ou vários registros de OS corretivas. FK: `ordens_servico.equipamento_id`.
- R33: Cada registro de OS corretivas aponta para zero ou um registro de Tipos de problema. Cada registro de Tipos de problema pode ser referenciado por zero, um ou vários registros de OS corretivas. FK: `ordens_servico.tipo_problema_id`.
- R37: Cada registro de Pendências da linha aponta para exatamente um registro de OS corretivas. Cada registro de OS corretivas pode ser referenciado por zero, um ou vários registros de Pendências da linha. FK: `pendencias_linha.ordem_servico_id`.
- R45: Cada registro de Solicitações de peças aponta para exatamente um registro de OS corretivas. Cada registro de OS corretivas pode ser referenciado por zero, um ou vários registros de Solicitações de peças. FK: `solicitacoes_pecas_manutencao.ordem_servico_id`.
- R46: Cada registro de Solicitações de peças aponta para exatamente um registro de Catálogo de peças. Cada registro de Catálogo de peças pode ser referenciado por zero, um ou vários registros de Solicitações de peças. FK: `solicitacoes_pecas_manutencao.peca_id`.

## Peças e compras

As peças ficam em um catálogo geral. A compra reúne itens; cada item escolhe uma peça e informa a quantidade.

Uma compra pode ser montada sem máquina e sem OS. Quando preenchida, ordem_servico_id aponta para a OS corretiva. No rascunho a compra pode ter zero itens; para enviar, a aplicação exige pelo menos um. A peça pode ter zero ou uma ficha técnica.

- R43: Cada registro de Solicitações de compra aponta para exatamente um registro de Usuários. Cada registro de Usuários pode ser referenciado por zero, um ou vários registros de Solicitações de compra. FK: `solicitacoes_compra.solicitante_id`.
- R19: Cada registro de Itens da compra aponta para exatamente um registro de Solicitações de compra. Cada registro de Solicitações de compra pode ser referenciado por zero, um ou vários registros de Itens da compra. FK: `itens_solicitacao_compra.solicitacao_id`.
- R20: Cada registro de Itens da compra aponta para exatamente um registro de Catálogo de peças. Cada registro de Catálogo de peças pode ser referenciado por zero, um ou vários registros de Itens da compra. FK: `itens_solicitacao_compra.peca_id`.
- R12: Cada registro de Histórico da compra aponta para exatamente um registro de Solicitações de compra. Cada registro de Solicitações de compra pode ser referenciado por zero, um ou vários registros de Histórico da compra. FK: `eventos_solicitacao_compra.solicitacao_id`.
- R17: Cada registro de Fichas técnicas das peças aponta para exatamente um registro de Catálogo de peças. Cada registro de Catálogo de peças pode ser referenciado por zero ou um registro de Fichas técnicas das peças. FK: `fichas_tecnicas_pecas.peca_id`.

## Acesso e histórico

Usuários identificam os responsáveis. Anexos pertencem ao equipamento; movimentações preservam de onde a máquina saiu e para onde foi.

A linha do usuário pode estar vazia no banco; uma restrição exige linha para o perfil OPERADOR. Em movimentações, origem e destino podem estar vazios. Os vínculos de autoria estão listados abaixo, separados da estrutura principal.

- R49: Cada registro de Usuários aponta para zero ou um registro de Linhas de produção. Cada registro de Linhas de produção pode ser referenciado por zero, um ou vários registros de Usuários. FK: `usuarios.linha_id`.
- R03: Cada registro de Fotos e manuais aponta para exatamente um registro de Equipamentos. Cada registro de Equipamentos pode ser referenciado por zero, um ou vários registros de Fotos e manuais. FK: `anexos_equipamento.equipamento_id`.
- R22: Cada registro de Movimentações aponta para exatamente um registro de Equipamentos. Cada registro de Equipamentos pode ser referenciado por zero, um ou vários registros de Movimentações. FK: `movimentacoes_equipamento.equipamento_id`.

## Compatibilidade existente

Esta associação já existe no esquema, mas não é exigida nem gravada pela aba Spare Parts da preventiva.

A chave primária é a combinação equipamento_id + peca_id. Ela impede repetir o mesmo par; não torna uma peça exclusiva de uma máquina. O catálogo e a lista de compra continuam independentes deste vínculo.

- R07: Cada registro de Compatibilidade antiga aponta para exatamente um registro de Equipamentos. Cada registro de Equipamentos pode ser referenciado por zero, um ou vários registros de Compatibilidade antiga. FK: `compatibilidade_pecas_equipamentos.equipamento_id`.
- R08: Cada registro de Compatibilidade antiga aponta para exatamente um registro de Catálogo de peças. Cada registro de Catálogo de peças pode ser referenciado por zero, um ou vários registros de Compatibilidade antiga. FK: `compatibilidade_pecas_equipamentos.peca_id`.

## Tabelas internas — 5

Estas cinco entidades são mantidas pelo Django. Seus nomes físicos continuam originais, mas os títulos abaixo explicam a função em português. Não substituem os perfis Administrador, Técnico e Operador do MANTIS.

Grupos e permissões são estruturas nativas do Django. Tipos de registro identificam os modelos. Histórico de migrações registra quais versões da estrutura foram aplicadas; ele não guarda o histórico de edições dos equipamentos.

- R04: Cada registro de Permissões dos grupos aponta para exatamente um registro de Permissões do Django. Cada registro de Permissões do Django pode ser referenciado por zero, um ou vários registros de Permissões dos grupos. FK: `auth_group_permissions.permission_id`.
- R05: Cada registro de Permissões dos grupos aponta para exatamente um registro de Grupos de permissões. Cada registro de Grupos de permissões pode ser referenciado por zero, um ou vários registros de Permissões dos grupos. FK: `auth_group_permissions.group_id`.
- R06: Cada registro de Permissões do Django aponta para exatamente um registro de Tipos de registro do Django. Cada registro de Tipos de registro do Django pode ser referenciado por zero, um ou vários registros de Permissões do Django. FK: `auth_permission.content_type_id`.
