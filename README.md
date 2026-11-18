# MANTIS

Sistema de manutenção industrial com interface Angular em `frontend`, API Django em `backend` e banco PostgreSQL.

## Executar no Windows

Use Python 3.12 ou superior, Node.js compatível com o Angular e Docker Desktop. Em um terminal, abra a pasta `backend` e execute:

```powershell
.\start.ps1
```

Em outro terminal, abra `frontend`:

```powershell
npm ci
npm start
```

A interface fica em <http://localhost:4200>. O Angular encaminha `/api` para o Django na porta 8000. A API informa sua disponibilidade em <http://127.0.0.1:8000/api/health>.

## Atualizar uma instalação existente

O inicializador aceita o `.env` anterior na raiz com variáveis `BD_*` e usa o volume original do Compose. Em instalações novas, ele cria `backend/.env` e usa o PostgreSQL na porta 5434. Faça backup do banco existente antes de iniciar a atualização, pois o inicializador aplica migrações.

As migrações `0030` a `0032` reconciliam o histórico do projeto com o esquema da versão nova. Os saldos globais anteriores passam a ter saldo no setor técnico `ESTOQUE-DEMO`, junto das movimentações e compras anteriores sem setor. A migração de preventivas atualiza o vencimento das agendas anuais ativas sem ordem aberta conforme a regra da nova versão.

## Documentação

- [Backend](backend/README.md) para configuração, rotas e testes.
- [Frontend](frontend/INSTRUCTIONS.md) para desenvolvimento e compilação.
- [Documentação do projeto](docs/README.md) para os guias de domínio mantidos no repositório.
