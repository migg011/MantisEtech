# Projeto Mantis

Sistema de gestão de manutenção industrial, equipamentos, linhas SMT e peças de reposição.

## Estrutura

- `frontend`: interface Angular.
- `backend`: API Django, migrações e testes.
- [Estrutura do backend](backend/ESTRUTURA.md): organização DRF com serviços por domínio.
- `docs`: documentação funcional, banco PostgreSQL, diagramas e material de apresentação.
- [Índice da documentação](docs/README.md): guias funcionais e referências históricas do banco.

## Novidades na branch dev

A branch `dev` reúne um conjunto de features portadas da cópia de apresentação, seguindo a estrutura do origin:

- Vínculo entre usuário e setor, restringindo a visibilidade de equipamentos e o fechamento de OS ao setor da conta.
- Faixas em tensão, frequência e pressão do equipamento e nova categoria `ELECTRICAL` para anexar o esquema elétrico.
- Cadastro de **feeders** com dados Panasonic (modelo, série, tipo de fita, código do fabricante) e histórico de preventiva/conserto por feeder.
- Sessão de operador no totem (`/api/operator-sessions`) para registrar quem está logado em qual linha.
- Horário planejado na agenda de preventiva, aproveitado na geração das ordens.
- Registro de atividades (`/api/activity-log`) com gravação automática em POST/PATCH/DELETE bem-sucedidos.
- Entrada de peças por nota fiscal (`/api/spare-parts/receipts`), gravando vários movimentos de estoque em uma transação.
- Comando `seed_demo` que preenche o banco com cadastros fictícios para a apresentação.
- Deploy de demonstração no Render (`backend/Dockerfile.demo` + `render.yaml`).

Veja `backend/ESTRUTURA.md` para onde cada peça encaixa na arquitetura DRF.

## Executar localmente

Consulte os pré-requisitos e detalhes em [backend/README.md](backend/README.md) .

No primeiro terminal PowerShell:

```powershell
cd backend
.\start.ps1
```

No segundo terminal:

```powershell
cd frontend
npm ci
npm start
```

Acesse `http://localhost:4200`. O Angular consulta a API em `127.0.0.1:8000`; o banco é PostgreSQL. Os arquivos `.env.example` orientam a configuração. Credenciais reais, bancos e backups não fazem parte do repositório.

## Principais módulos

- Autenticação e perfis de acesso.
- Setores, equipamentos, linhas SMT e totem de operação.
- Ordens de serviço corretivas e preventivas, calendário e checklists.
- Spare Parts com fotos, categorias, movimentações de estoque e inventário.
- Solicitações de peças e compras.
- Dashboard e documentação do banco de dados.

Consulte [as categorias](docs/CATEGORIAS_SPARE_PARTS.md), [o estoque](docs/ENTRADA_PECAS.md) e [as propostas de reposição](docs/PROPOSTA_REPOSICAO_E_COMPRAS.md) para distinguir funcionalidades entregues das próximas etapas. Integração com IA e reposição automática permanecem em planejamento.

## Testes

Dentro de `backend`:

```powershell
.\.venv\Scripts\python.exe manage.py test --settings=config.test_postgres --noinput
```

Dentro de `frontend`:

```powershell
npm run build
```

O repositório é privado. A publicação do código não hospeda a aplicação nem transfere o banco de dados operacional.


