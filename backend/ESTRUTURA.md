# Backend Mantis

A organização separa configuração, domínio, interface
REST e serviços. Os modelos, campos, relacionamentos e migrações do Mantis foram
mantidos. O app continua registrado como `maintenance` para preservar
`AUTH_USER_MODEL`, imports e histórico das migrações.

```text
backend/
├── manage.py
├── requirements.txt / requirements.lock.txt
├── config/                         # Configuração do projeto
│   ├── settings.py                 # Ambiente, PostgreSQL, DRF, CORS, idioma
│   ├── urls.py                     # Inclui as URLs do domínio
│   ├── wsgi.py / asgi.py
│   ├── test_settings.py            # SQLite em memória
│   └── test_postgres.py            # PostgreSQL exclusivo de testes
└── maintenance/
    ├── models.py                   # Modelos e relacionamentos existentes
    ├── serializers.py              # Leitura e validação de entradas
    ├── views.py                    # Login, identidade, saúde e painel
    ├── viewsets.py                 # Recursos e ações REST
    ├── urls.py                     # DefaultRouter e contratos do Angular
    ├── urls_v1.py                  # Aliases da API v1
    ├── filters.py                  # FilterSets por recurso
    ├── authentication.py           # Autenticação Bearer do DRF
    ├── permissions.py              # Conta ativa, equipe e administrador
    ├── exceptions.py               # Erros de domínio e tratamento HTTP
    ├── renderers.py                # JSON com contrato de datas/decimais
    ├── forms.py                    # Validadores existentes dos cadastros
    ├── services/
    │   ├── base.py                 # OperationContext e Result
    │   ├── common.py               # Visibilidade e conversões
    │   ├── authentication.py
    │   ├── users.py
    │   ├── organization.py         # Setores, linhas, máquinas e anexos
    │   ├── corrective.py           # OS, atendimento e pendências
    │   ├── parts.py                # Catálogo, categorias e inventário
    │   ├── purchases.py
    │   ├── registrations.py        # Transações de montagem e aprovação
    │   ├── stock.py
    │   ├── preventive_schedule.py
    │   ├── preventive.py
    │   ├── preventive_orders.py
    │   ├── dashboard.py
    │   └── operations.py           # Exporta os casos de uso para as views
    ├── document_templates/
    ├── portuguese_names.py
    ├── calendar_source.py
    ├── er_diagrams.py
    ├── migrations/                 # Histórico existente, sem reescrita
    ├── management/commands/
    └── tests/
```

## Fluxo e responsabilidades

`Angular → urls → APIView/ViewSet → serializer → serviço → ORM → PostgreSQL`

Views convertem os dados HTTP em `OperationContext`: usuário, método, parâmetros,
dados JSON e origem. Serviços podem ser chamados sem construir uma requisição
HTTP. Downloads continuam sendo produzidos pelos serviços de documentos/anexos.

Os cadastros reaproveitam as validações de `forms.py` através de
`FormValidationSerializer`, preservando regras de senha, precisão, arquivos,
proteção da própria conta e campos omitidos no PATCH. Não há renderização de
formulários Django. Montagem, transferência, estoque e requisição de peça também
possuem serializers de entrada explícitos.

Serializers de leitura usam listas explícitas de campos e não expõem senha/hash
ou conteúdo binário. Escritas passam pelos casos de uso para preservar histórico,
saldo e transições de estado.

## Contratos preservados

- Login: `POST /api/auth/login` com `registration` e `password`.
- Autenticação: `Authorization: Bearer <token>`, com oito horas de validade.
- Troca de senha ou desativação invalida o acesso. Cookies não autenticam a API.
- URLs do Angular sem barra final; listagens sem envelope de paginação.
- Erros `{error, details?}`, datas ISO e decimais no formato anterior.
- Aliases v1 com barra final, como `/api/v1/users/` e `/api/v1/equipments/`,
  reutilizam serviços e permissões. Recursos auxiliares de anexos, movimentações,
  fichas e requisições oferecem leitura; escritas usam as ações de domínio.

Os comandos canônicos usam nomes em inglês: `create_admin`, `adopt_legacy`,
`map_database`, `prepare_preventive_calendar`, `document_database` e `generate_er`.
A implementação das regras fica em `services/`; os contratos HTTP e os nomes
físicos do banco permanecem inalterados.

## Ambiente e banco

O `.env` da raiz é compartilhado com Docker Compose e tem prioridade sobre o
`.env` de backend. Variáveis do processo têm prioridade sobre ambos.

Pode-se manter `DATABASE_URL` ou usar `BD_NOME`, `BD_USUARIO`, `BD_SENHA`,
`BD_HOST` e `BD_PORT`. Preencher `BD_NOME` seleciona a segunda
opção. O mecanismo continua sendo PostgreSQL.

A reorganização não aplica migrações no banco operacional nem cria contas.
Os nomes internos de categorias usam `MaterialCategory`, `SparePartCategory` e
`SparePart.categories`. A migração `0022_english_category_names` atualiza apenas
o estado do Django; mantém a tabela `categorias_pecas`, suas colunas e os vínculos
existentes. O histórico anterior de migrações conserva os nomes originais.
Como o banco foi zerado anteriormente, a preparação normal precisa executar as
migrações e criar o primeiro administrador antes do login.

## Validação

Na pasta `backend`, com o ambiente virtual ativado:

```powershell
python manage.py check
python manage.py test --settings=config.test_settings --noinput
python manage.py test --settings=config.test_postgres --noinput
```

O último comando usa `test_mantis_rest`, separado do banco operacional, e testa
migrações e concorrência no PostgreSQL. Exige permissão de criação de banco.
