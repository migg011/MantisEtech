# Guia de estudo: banco, backend, API e regras de negócio

Revisão inicial do código em 10/11/2026. Este guia explica o estado encontrado;
não substitui uma auditoria completa nem altera o comportamento do sistema.

## 1. O que você precisa conseguir explicar

“O Mantis gerencia manutenção industrial. O Angular envia requisições para uma
API Django REST Framework. A API autentica, verifica permissões e valida os
dados. Os serviços executam as regras de negócio e usam o ORM para acessar o
PostgreSQL. O banco mantém relacionamentos e restrições de integridade.”

API é a porta de comunicação, backend é a aplicação que processa as operações,
e banco é onde os dados persistem. Regra de negócio é uma condição do domínio:
por exemplo, não permitir retirar mais peças do que existem em estoque.

## 2. Árvore essencial — nesta ordem de estudo

```text
backend/
├── manage.py                 executa comandos Django
├── config/
│   ├── settings.py           configura banco, autenticação, DRF e ambiente
│   ├── urls.py               entrada do roteamento
│   └── test_postgres.py      testes em PostgreSQL separado
└── maintenance/
    ├── models.py             entidades, campos, vínculos e restrições
    ├── admin.py              painel administrativo e gerenciamento de contas
    ├── migrations/           histórico versionado do esquema
    ├── urls.py               endereços da API principal
    ├── urls_v1.py            endereços de compatibilidade
    ├── views.py              recebe HTTP e chama os serviços
    ├── viewsets.py           agrupa operações por recurso
    ├── serializers.py        valida entradas e descreve dados de saída
    ├── forms.py              validações de cadastro reaproveitadas pela API
    ├── authentication.py     valida o token Bearer
    ├── backends.py           verifica matrícula/senha e hashes antigos
    ├── permissions.py        controla quem pode acessar
    ├── exceptions.py         transforma erros em respostas HTTP
    ├── renderers.py          converte dados para JSON
    ├── services/             regras e operações do sistema
    ├── tests/                verificações automatizadas
    └── management/commands/  ferramentas administrativas
```

Não comece por `er_diagrams.py`, arquivos de apresentação ou SQL legado.
Eles não são o melhor caminho para entender uma requisição normal.

### Serviços prioritários

| Arquivo em `services/` | Responsabilidade |
|---|---|
| `base.py` | `OperationContext` carrega entrada; `Result` carrega dados e status |
| `common.py` | Funções compartilhadas, incluindo escopo de visibilidade |
| `organization.py` | Setores, linhas, equipamentos e anexos |
| `registrations.py` | Operações de cadastro, montagem e aprovação |
| `corrective.py` | Ordens corretivas, atendimento e pendências |
| `parts.py` | Catálogo, categorias, inventário e entrada HTTP de estoque |
| `stock.py` | Cálculo de saldo, bloqueio e registro de movimentação |
| `preventive_orders.py` | Emissão e execução de ordens preventivas |
| `purchases.py` | Solicitações de compra |
| `operations.py` | Reexporta operações para a camada HTTP |

## 3. Como os dados chegam ao banco

```text
Requisição HTTP
  → URL seleciona a view
  → autenticação e permissões
  → validação da entrada
  → serviço executa a regra
  → ORM consulta/grava no PostgreSQL
  → resultado vira resposta HTTP/JSON
```

ORM significa mapeamento objeto-relacional: permite representar tabelas como
classes e consultar usando Python. Isso não elimina SQL nem a necessidade de
entender índices, relacionamentos e transações.

Há uma particularidade importante: várias views retornam dicionários montados
pelos serviços. Nem toda resposta passa pelo `ModelSerializer` declarado no
ViewSet. Para conhecer a resposta real, siga `self.execute(...)` até o serviço
e confira os testes da rota.

## 4. Banco: conceitos com exemplos reais

| Conceito | Exemplo no Mantis |
|---|---|
| Chave primária (PK) | `id` identifica um registro |
| Chave estrangeira (FK) | Um equipamento aponta para um setor e, opcionalmente, uma linha |
| Um para muitos | Uma linha pode ter vários equipamentos |
| Muitos para muitos | Uma peça pode ter várias categorias, e uma categoria várias peças |
| Tabela associativa | `SparePartCategory` representa o vínculo peça/categoria |
| Restrição única | Não repetir a posição de equipamentos na mesma linha |
| Restrição de verificação | Saldo não negativo; operador precisa de linha |
| Proteção de exclusão | Vários relacionamentos usam `PROTECT` para impedir apagar referências necessárias |

`Equipment` é a classe Python; `equipamentos` é sua tabela física.
`db_table` e `db_column` fazem essa correspondência. Essa diferença de idioma
não indica duplicação de dados nem erro de modelagem.

As migrações registram a evolução do esquema. Alterar `models.py` não atualiza
sozinho um banco existente: é necessário criar/revisar a migração e aplicá-la.
Não apague migrações antigas para “limpar” o projeto.

`NULL` e zero não são equivalentes: no estoque, `NULL` significa que a contagem
inicial ainda não foi registrada; zero significa saldo conhecido e zerado.

## 5. Demonstração principal: saída de estoque

Rota: `POST /api/spare-parts/{id}/stock-movements`.
Exemplo ilustrativo, para uma peça já inicializada e uma conta autorizada:

```json
{
  "kind": "SAIDA",
  "quantity": "2.000",
  "requestKey": "07bfa900-7856-4f8e-94a1-8e76b8796340",
  "note": "Uso na manutenção"
}
```

1. O Bearer identifica a conta; a operação de escrita exige administrador.
2. `StockInputSerializer` verifica tipos e formato dos campos.
3. `parts.stock_movements` chama `stock.record_movement`.
4. O serviço valida quantidade, tipo, data e demais regras.
5. `transaction.atomic()` agrupa as gravações em uma transação.
6. `select_for_update()` bloqueia a peça durante a operação no PostgreSQL.
7. O serviço verifica a chave de repetição e calcula o saldo.
8. Grava a movimentação e atualiza o saldo; retorna o resultado.

Se o saldo é 5, retirar 2 resulta em 3. Retirar 6 é rejeitado.
Uma falha dentro da transação desfaz suas gravações: não deve ficar histórico
gravado sem a atualização correspondente do saldo.

**Concorrência:** duas pessoas podem retirar peças ao mesmo tempo. O bloqueio
faz as operações sobre a mesma peça serem processadas em sequência, evitando
que ambas calculem usando o mesmo saldo antigo.

**Idempotência:** repetir a mesma operação com a mesma `requestKey` não deve
retirar novamente. O serviço compara também os dados e o autor. Uma operação
nova retorna 201 e `replayed: false`; a repetição reconhecida retorna 200 e
`replayed: true`. Reutilizar a chave com dados diferentes é rejeitado.

## 6. Respostas e segurança da API

| Código | Significado prático |
|---|---|
| 200 | Consulta ou operação concluída |
| 201 | Novo registro criado |
| 400 | Entrada ou regra inválida |
| 401 | Autenticação ausente ou inválida |
| 403 | Conta sem permissão para a ação |
| 404 | Recurso não encontrado |
| 405 | Método não permitido |
| 409 | Conflito com o estado ou integridade dos dados |

Erros tratados seguem `{ "error": "mensagem", "details": ... }`, com `details`
opcional. Exceções inesperadas não são automaticamente convertidas nesse mesmo
contrato pelo manipulador próprio; não prometa que todo erro possível tem esse formato.

Autenticação responde “quem é você?”. Autorização responde “o que pode fazer?”.
Ocultar um botão no Angular não substitui verificar a permissão no servidor.

O token usa assinatura do Django, enviado em `Authorization: Bearer ...`.
Não o descreva como JWT: não é essa a implementação encontrada.
Tem validade configurada de oito horas. A validação consulta conta ativa e
compara o hash de autenticação, invalidando o acesso após troca de senha.
Assinatura impede adulteração; não significa que o conteúdo esteja criptografado.

Quantidades decimais são mantidas com `Decimal`; a API configura decimais como
texto no JSON. Evita-se usar ponto flutuante binário para representar esses valores.
Datas usam representação ISO. Senhas e conteúdo binário não fazem parte dos
campos dos serializers de leitura examinados.

## 7. Revisão inicial de consistência

### Proteções encontradas

- Estoque: validação no serviço, transação, bloqueio de linha, chave única de
  requisição e restrições de saldo no modelo.
- Equipamento: combinação linha/posição única e verificação da alocação válida.
- Preventiva: restrição de uma ordem aberta por agenda.
- Permissões: verificações HTTP e também nos casos de uso decorados.
- Contratos: testes para login, aliases v1, filtros, permissões e ausência de
  campos sensíveis nos serializers.

### Pontos de atenção — não são todos defeitos

1. `views.OperationMixin.execute` valida com serializer, mas entrega os dados
   originais ao serviço, não `validated_data`. Os serviços fazem conversões
   próprias. Isso aumenta o risco de divergência futura. Trocar diretamente
   por `validated_data` exige revisar tipos esperados, como data e UUID.
2. Entradas como `sparePartId` usam camelCase; várias saídas usam snake_case.
   É um contrato existente, não algo para renomear sem ajustar consumidores.
3. Há múltiplas formas de montar saídas: serializers e dicionários dos serviços.
   Uma alteração no serializer não garante alteração na resposta principal.
4. Não há paginação global, mas algumas consultas têm cortes: movimentações
   de peça retornam até 100; a consulta de OS por linha inclui até 20 concluídas.
   O inventário tem outro escopo. Não confunda listagem da tela com histórico completo.
5. `IntegrityError` recebe mensagem genérica e status 409. É consistente como
   categoria de conflito, mas não identifica precisamente toda restrição violada.
6. Diagramas antigos em `docs/database` não são prova do esquema atual. Use
   modelos, migrações e, quando necessário, introspecção do banco do ambiente.

Na execução de testes imediatamente anterior a esta revisão, a suíte SQLite
teve 107 testes, sem falhas e com seis ignorados. Isso não comprova sozinho
concorrência no PostgreSQL nem consistência de todos os registros operacionais.
Esta revisão não consultou os dados reais nem executou novas migrações.

## 8. Plano de oito dias

| Dia | Estudo | Entrega para você mesmo |
|---|---|---|
| 1 | Árvore e fluxo HTTP → banco | Desenhar o fluxo sem olhar |
| 2 | `models.py`: setor, linha, equipamento, usuário | Explicar PK, FK e cardinalidade |
| 3 | Peças, categorias e movimentações | Explicar NULL, zero, Decimal e tabela associativa |
| 4 | URLs, views, serializers e erros | Explicar uma requisição e os códigos HTTP |
| 5 | Login e permissões | Distinguir autenticação, autorização e token |
| 6 | Estoque e transações | Simular duas saídas concorrentes e uma repetição |
| 7 | OS, preventiva e testes | Seguir uma transição de estado até a gravação |
| 8 | Simulado de banca | Responder em voz alta e localizar arquivos sem ajuda |

Reserve 60–90 minutos por dia. Leia uma função, explique com suas palavras e
localize um teste relacionado. Isso vale mais que memorizar nomes isolados.

## 9. Perguntas para treinar

- **Onde fica a regra de saldo?** Em `services/stock.py`, com restrições adicionais no banco.
- **Por que não validar só no frontend?** A API pode ser chamada diretamente; o servidor deve proteger os dados.
- **Por que serviço separado da view?** Separa o protocolo HTTP das operações de negócio e facilita testes e reutilização.
- **Por que transação?** Para confirmar ou desfazer juntas as gravações relacionadas.
- **Por que o banco também precisa de restrições?** Para impedir estados inválidos mesmo diante de erros ou concorrência na aplicação.
- **O que acontece com duas saídas simultâneas?** O bloqueio da peça serializa as alterações dentro das transações.
- **Posso apagar uma tabela antiga ou uma migração?** Só com análise de dependências e evolução controlada, nunca apenas por parecer sem uso.
- **Tudo está garantido pelos testes?** Não. Eles verificam cenários conhecidos; banco real, concorrência e casos novos exigem validação apropriada.

Se não souber uma resposta, diga qual camada investigaria. Não atribua ao projeto
funcionalidades que ele ainda não implementa, como baixa automática de estoque
apenas por solicitar uma peça em uma OS.

## Django Admin

O painel fica em `http://127.0.0.1:8000/admin/`. O login usa matrícula e senha.
Somente contas ativas com perfil ADMINISTRADOR podem entrar; os administradores
existentes já têm esse acesso. Os perfis do Mantis determinam as permissões,
sem exigir campos novos no modelo de usuário.

Depois de `python manage.py migrate`, crie a primeira conta com
`python manage.py create_admin` ou use `python manage.py createsuperuser`.
O comando `migrate` também instala as tabelas de histórico do Django Admin.

O painel permite criar e editar usuários e trocar senhas com hash e validação.
Contas são desativadas, não excluídas. Os modelos operacionais ficam somente
para consulta: estoque, compras e ordens devem ser alterados pelos serviços da
API, que aplicam as regras de negócio.

A tabela de compatibilidade peça/equipamento usa chave primária composta e não
é registrada no Admin, que não suporta esse tipo de chave. Os demais 23 modelos
do domínio estão registrados. A interface principal continua sendo Angular.
