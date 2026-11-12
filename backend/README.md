# MANTIS �?" API Django para o Angular

Este diretório contém exclusivamente o backend: API JSON, autenticação, validação, regras de negócio, modelos e migrações PostgreSQL. As telas operacionais ficam em `../frontend` (Angular). O Django também fornece o painel administrativo `/admin/`.

A API mantém os caminhos e os formatos de dados consumidos pelo Angular. A estrutura utiliza views/viewsets DRF, serializers, filtros, permissões e serviços. Consulte [ESTRUTURA.md](ESTRUTURA.md) para navegar pelo backend.

## Iniciar no Windows

Pré-requisitos: Python 3.12+ e Docker Desktop iniciado. Nesta pasta:

```powershell
.\start.ps1
```

O script prepara `.venv`, instala `requirements.lock.txt`, cria `.env` com segredos aleatórios se necessário, inicia o PostgreSQL exclusivo, executa migrações e solicita o primeiro administrador. A senha exige pelo menos 12 caracteres e passa pelos validadores do Django. Não há conta ou senha padrão.

Em outro terminal, na pasta `../frontend`:

```powershell
npm install
npm start
```

Interface: **http://localhost:4200**. API: **http://127.0.0.1:8000/api/health**. O proxy Angular encaminha `/api` para a porta 8000. O Django Admin fica em http://127.0.0.1:8000/admin/, com acesso por matrícula e senha de administrador ativo.

O banco padrão usa porta **5433**, nome `mantis` e o serviço `postgres` de `docker/compose.yml`. O `.env` da raiz configura Django e Docker; ambos usam os campos `BD_*`.

## Instalação manual

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
Copy-Item ..\.env.example ..\.env
```

Configure `DJANGO_SECRET_KEY` (32+ caracteres), `POSTGRES_PASSWORD` e a mesma senha em `DATABASE_URL`. Codifique caracteres reservados na URL. O inicializador usa senhas hexadecimais para evitar esse problema. Depois:

```powershell
docker compose --env-file ../.env -f docker/compose.yml up -d --wait postgres
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py create_admin
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

`create_admin` só é necessário na primeira configuração. Não execute comandos que removam volumes de bancos cujos dados deseja preservar.

## Autenticação e contrato

`POST /api/auth/login` recebe JSON com `registration` e `password`; retorna `{ "token": "...", "user": { "id": 1, "name": "Administrador", "registration": "ADM", "role": "ADMINISTRADOR", "lineId": null, "active": true } }`. O Angular guarda o token em `sessionStorage` e o envia no cabeçalho `Authorization: Bearer <token>`. As demais respostas seguem os nomes de campos usados pelas telas atuais, incluindo `sector_id`, `line_id` e `equipment_count`.

Os tokens são assinados pelo Django e expiram em oito horas. Não são os JWTs da antiga API Express: entre novamente após mudar de backend. A API consulta a conta a cada requisição; desativação e redefinição de senha invalidam o acesso. Logout no Angular remove os dados locais. Cookies e sessões Django não autenticam a API; por isso operações exigem o cabeçalho explícito e não dependem de cookies CSRF. Não habilite autenticação por cookie sem revisar essa proteção.

Rotas principais, sem barra final:

| Recurso | Rotas |
| --- | --- |
| Saúde e usuário atual | `GET /api/health`, `GET /api/me` |
| Login | `POST /api/auth/login` |
| Setores | `GET/POST /api/sectors`, `PATCH/DELETE /api/sectors/:id` |
| Linhas | `GET/POST /api/lines` |
| Montagem | `POST /api/lines/:id/equipment`, `DELETE /api/lines/:id/equipment/:equipmentId`, `POST /api/lines/:id/dismantle` |
| Equipamentos | `GET /api/equipment-types`, `GET/POST /api/equipment`, `PATCH/DELETE /api/equipment/:id` |
| Anexos e histórico | `GET /api/equipment/:id/attachments`, `PUT /api/equipment/:id/attachments/:kind`, `GET /api/equipment/:id/attachments/:kind/download`, `GET /api/equipment/:id/movements` |
| Usuários | `GET/POST /api/users`, `PATCH /api/users/:id`, `PATCH /api/users/:id/status`, `PATCH /api/users/:id/password` |
| OS | `GET/POST /api/orders`, `PATCH /api/orders/:id` |
| Problemas de manutenção | `GET/POST /api/problem-types`, `PATCH/DELETE /api/problem-types/:id` |
| Atendimento e peças da OS | `GET /api/orders/:id`, `GET /api/orders/:id/spare-parts`, `GET/POST /api/orders/:id/part-requisitions` |
| Peças | `GET/POST /api/spare-parts`, `PATCH/DELETE /api/spare-parts/:id` |
| Fichas técnicas | `GET /api/spare-purchase/parts`, `GET/PUT /api/spare-purchase/parts/:id/technical`, `POST /api/spare-purchase/parts/:id/validate` |
| Compras | `GET /api/spare-purchase/managers`, `GET/POST /api/spare-purchase/requests`, `GET/PATCH /api/spare-purchase/requests/:id` |
| Envio, decisão e CSV | `POST /api/spare-purchase/requests/:id/submit`, `POST /api/spare-purchase/requests/:id/decision`, `GET /api/spare-purchase/requests/:id/export.csv` |

Criações/edições recebem JSON com os nomes camelCase que o Angular já envia. Anexos usam `{filename, mimeType, base64}`; `kind` é `PHOTO` ou `MANUAL`. Compras recebem `items: [{sparePartId, quantity, itemNote}]`; a API aceita várias peças e edição de rascunho. A tela Angular atual cria uma peça por solicitação. Erros retornam `{error, details?}` com HTTP 400/401/403/404/405/409/415/429; anexos e CSV são downloads binários, não JSON.

## Permissões e regras

No atendimento técnico da OS, administrador/técnico registram causa raiz, solução corretiva e solução preventiva. A seção **Spare Parts e solicitações** registra a solicitação de peça diretamente com quantidade, solicitante, observação, OS, máquina e serial histórico. Não cria compra, não gera rascunho e não exige gestor. O servidor determina máquina e serial a partir da OS. Solicitação de compra é um processo separado em **Solicitações de compra**, onde permanecem rascunho, ficha técnica e aprovação. Solicitar uma peça não registra retirada ou consumo de estoque.

Novas OS exigem `equipmentId` e `problemTypeId`, correspondentes a um equipamento acessível e a um problema ativo do catálogo. A descrição é copiada do catálogo para preservar o histórico. O operador recebe a prioridade padrão do problema; administrador/técnico podem informar `priority`. Problemas podem valer para todos os equipamentos ou para um tipo específico. A equipe mantém o catálogo em **Central de Cadastros �?' Problemas de manutenção**, inclusive edição, desativação e reativação. As migrações incluem oito opções iniciais editáveis e preservam as OS anteriores.

Administrador gerencia usuários e os cadastros mestres. Técnico pode criar setores, linhas e equipamentos, montar linhas, atender OS e manter fichas técnicas; não altera/exclui os cadastros mestres. Operador só consulta as máquinas/OS da linha ativa atribuída e abre OS nela. Pode solicitar compra vinculada a uma OS da própria linha pela API.

Alocação exige equipamento disponível no mesmo setor, posição positiva e livre; transações preservam histórico. Fotos PNG/JPG têm limite de 3 MB e manuais PDF de 5 MB, com verificação de assinatura. Um novo anexo substitui o da mesma categoria. Compras exigem ficha completa; importação exige NCM, descrição PLI e validação interna. Envio congela os dados técnicos; decisão é exclusiva do gestor designado. CSV neutraliza fórmulas de planilha.

## Usar dados da implementação anterior

Adoção foi preparada para as tabelas originais, inclusive senhas bcrypt, atualizadas no primeiro login. **Trabalhe primeiro com um backup restaurado em outro banco.** A conversão do banco real não faz parte desta alteração. Configure a conexão da cópia em `DATABASE_URL` e um novo `DJANGO_SECRET_KEY`; não copie o `.env` do Express.

Na cópia restaurada, antes de `migrate`:

```powershell
.\.venv\Scripts\python.exe manage.py adopt_legacy
```

O comando reaplica os sete scripts SQL aditivos, adiciona `users.last_login`, registra a migração inicial com `--fake-initial` e executa as demais migrações. Não elimina cadastros. Para banco novo vazio, use apenas `migrate`. Reversão de uma adoção deve ser feita restaurando backup, sem reverter migrações de tabelas adotadas.

## Docker e execução da API

O Compose atual, na raiz, inicia o PostgreSQL. A API é executada pelo inicializador ou por `manage.py runserver`; o Angular roda separadamente. O `Dockerfile` de backend permanece disponível para construir uma imagem da API com Waitress, mas o Compose atual não declara um serviço `web`.

Em produção, sirva o build Angular por um servidor web e encaminhe `/api` para o Django na mesma origem. Configure HTTPS, `DJANGO_DEBUG=false`, `DJANGO_ALLOWED_HOSTS` e as origens permitidas conforme o ambiente.

## Testes

Teste isolado em SQLite na memória, sem tocar no banco configurado:

```powershell
.\.venv\Scripts\python.exe manage.py test --settings=config.test_postgres
```

Teste com PostgreSQL exclusivo de desenvolvimento, incluindo migrações e concorrência:

```powershell
.\.venv\Scripts\python.exe manage.py test
```

O segundo comando cria um banco `test_<nome configurado>` e exige permissão para criar bancos. O teste de concorrência é pulado no SQLite.

## Ficha do equipamento na preventiva

Em **Central de Cadastros �?' Check List de Preventiva**, a área **Equipamentos** abre a ficha automaticamente ao selecionar uma máquina, inclusive sem preventiva configurada. A navegação separa **Equipamentos**, **Cronograma** e **Ordens de serviço**; os indicadores de prazo filtram o cronograma. Listas de agenda e OS mostram inicialmente oito registros, com a ação **Mostrar mais 8**. Os dados técnicos extensos e o histórico geral de execuções ficam recolhidos até serem expandidos. O botão **Ficha** no cronograma também abre a identificação do equipamento. As abas dão acesso ao checklist e à emissão da OS, à foto/manual e ao histórico de movimentações e OS preventivas carregadas. O histórico de OS preserva o recorte da listagem existente: todas as abertas e as últimas 100 encerradas.

A aba **Spare Parts** pesquisa o catálogo geral disponível para compras por código, part number, descrição, fabricante ou categoria. Não filtra nem cria compatibilidade com a máquina. Selecione até 100 peças, informe quantidades, gestor e justificativa e use **Gerar solicitação de compra**. A operação cria um único rascunho com todos os itens, sem equipamento ou OS vinculados; envio, ficha técnica e aprovação permanecem em **Solicitações de compra**. A lista não movimenta estoque e permanece temporária até gerar o rascunho: sair ou recarregar a página descarta os itens ainda não gravados.

Os comentários dos componentes explicam a seleção das abas, as consultas autenticadas, o uso de Blob nos anexos e a diferença entre a lista local e o rascunho salvo na API.

## Calendário de programação

Na área **Cronograma**, o calendário oferece duas bases: **Modelo da planilha · 2026** e **Equipamentos cadastrados**. A proposta de 2026 foi preparada a partir de `Check List de Manutenção Preventiva 2025.xlsx`, preservando dia, mês, horário, seção, referência da máquina, técnico e atividades. São 312 propostas; 35 não informam periodicidade e uma linha sem data válida foi excluída com aviso. Fins de semana e inconsistências nas datas realizadas da origem são sinalizados para revisão. Esses dados não comprovam execução em 2026.

O modelo não cria máquinas, usuários, agendas ou OS, nem tenta associar nomes da planilha aos cadastros atuais. Não é uma agenda operacional confirmada ou uma validação da capacidade da equipe. Selecionar **2027** consulta as agendas reais: próximos vencimentos cadastrados e datas das OS abertas. Não projeta ciclos que ainda não foram registrados. Em eventos reais, a ação de OS reutiliza a emissão e o preenchimento existentes.

Para preparar novamente a referência, sem alterar a planilha original ou o banco:

```powershell
.\.venv\Scripts\python.exe manage.py prepare_preventive_calendar --source "CAMINHO\Check List de Manutenção Preventiva 2025.xlsx"
```

O comando atualiza `maintenance/document_templates/preventive_calendar_2026.json`. A leitura dessa base usa `GET /api/preventive-calendar-template`, restrito a técnico e administrador. O calendário permite navegar por mês, pesquisar e filtrar seção e periodicidade; selecione um dia e uma atividade para consultar a origem, os avisos e o checklist.

## Limites

Não inclui notificações externas, PDF, QR Code, IA, emissão automática de OS pelo calendário ou MTBF. Estoque possui movimentações e inventário; o painel calcula MTTR pela duração dos atendimentos concluídos. O limite de login usa cache local por processo; produção com vários processos exige cache compartilhado e limitação no proxy. Anexos dependem do backup PostgreSQL. Validação de assinatura não é antivírus. `runserver` e o inicializador são para desenvolvimento local.


### Identificação e tempos do atendimento

A abertura da OS representa o início da parada. Em **Ordens de serviço �?' Atender**, o técnico ou administrador conectado confirma sua própria matrícula e senha em **Iniciar atendimento** (`POST /api/orders/:id/start`). O servidor registra o responsável e `started_at` uma única vez. Abrir o modal não inicia o atendimento. Outra conta não pode assumir ou concluir essa OS. A OS concluída não pode ser reaberta por este fluxo.

O fechamento grava `finished_at` e `downtime_seconds` (abertura até fechamento, incluindo espera pelo técnico). O status da linha consulta `GET /api/orders?lineId=...` a cada 15 segundos, respeitando a linha do operador, exibindo todas as OS em aberto e as últimas 20 concluídas. O contador é por OS e não soma paradas simultâneas da linha. O navegador atualiza os minutos a cada segundo, tomando como referência o relógio do servidor; após concluir, o total fica fixo. O horário de abertura não é um horário de parada digitado retroativamente.


### Pendências de linha

Na lista de OS ou no atendimento, **Gerar pendência** registra descrição e prioridade. O servidor determina OS, máquina, serial e linha, ignorando IDs de contexto enviados pelo cliente. Máquina sem linha não pode gerar pendência de linha. O registro independe do fechamento da OS: concluir uma OS não resolve suas pendências automaticamente.

Em **Central de Cadastros �?' Pendências de linha**, os registros são agrupados por linha, com pesquisa e filtros de linha/situação. **Registrar solução** salva o texto da solução, autor e horário. A linha e o serial de origem permanecem no histórico se a máquina for movida. Técnico e administrador podem consultar, registrar e resolver; o operador não acessa esse módulo.

Contratos: `GET/POST /api/orders/:id/pendencies`, `GET /api/line-pendencies?lineId=...&status=PENDENTE`, `PATCH /api/line-pendencies/:id` com `{status: "RESOLVIDA", resolution: "..."}`. A abertura de OS no painel da linha é feita pelo clique na máquina; os botões Nova OS e Atualizar foram removidos desse painel.

### Painel de status das linhas

A rota `/ordens` usa um painel no estilo de chegadas e partidas: ao vivo mostra todas as linhas ativas, uma linha por OS em aberto e indicação explícita de linhas sem OS aberta. O histórico separado mostra as últimas 100 OS concluídas. O atendimento é aberto pelo número da OS; **Gerar pendência** fica somente dentro do atendimento.

**Modo exposição** abre `/status-linhas` na mesma sessão autenticada, sem menu lateral ou cabeçalho administrativo. O botão **Tela cheia** permite ocupar o monitor. O painel consulta `GET /api/line-status` a cada 15 segundos e atualiza o contador a cada segundo. No modo de exposição as páginas alternam a cada 15 segundos, com quantidade de registros ajustada à altura da tela. Os dados de todas as OS ativas são retornados, sem o limite de 200 da listagem antiga. Operador visualiza somente sua linha. Falhas de conexão mostram um alerta explícito de dados desatualizados.
# Código em inglês e banco em português (migração 0012)

O login e as ações dos cadastros usam nomes em inglês, como
`login`, `save`, `edit`, `loadData` e `UserForm`.
As 21 tabelas de negócio e suas colunas físicas continuam em português:
`usuarios.matricula`, `usuarios.senha_hash`, `equipamentos.numero_serie`.

Os atributos ORM, as chaves HTTP/JSON e os nomes exigidos pelo Django/Angular
continuam compatíveis. Por exemplo, `User.registration` consulta
`usuarios.matricula` por meio de `db_column`. As migrações antigas e as tabelas
nativas do Django não foram traduzidas. Índices, restrições e sequências
preexistentes podem conservar os nomes antigos.

Antes de aplicar a migração em outro ambiente, faça backup completo daquele
banco; depois execute `python manage.py migrate`. Não edite migrações antigas.

Para atualizar o guia e os metadados sem exportar os registros:

```powershell
python manage.py map_database --output ../docs/database/generated
python manage.py document_database --output ../docs/database/generated
```

Consulte `docs/README.md` para localizar os guias mantidos e distinguir as referências históricas dos metadados gerados.

## Organização do código

Consulte [ESTRUTURA.md](ESTRUTURA.md) para seguir o caminho da informação da tela até o banco.
O frontend usa `features`, `core` e `shared`. As regras Django estão
organizadas por domínio em `maintenance/services/`.
Os comandos canônicos usam nomes em inglês: `create_admin`, `adopt_legacy`,
`map_database`, `prepare_preventive_calendar`, `document_database` e `generate_er`.

