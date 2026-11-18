> Documento histórico da implementação Angular + Express. Para a arquitetura ativa Angular + Django, siga o README.md da pasta mantis.

# MANTIS 2.0 — Fase 1 (versão de revisão)

## Entregue nesta versão
- Cadastro de setores (`/setores`) para Administrador e Técnico.
- Associação de um setor no momento do cadastro de uma linha SMT.
- Quantidade e comprimento total das máquinas por linha, calculados pelo PostgreSQL (comprimento em metros na tela, origem em milímetros no equipamento).
- Permissão de criação de linhas e equipamentos para Técnico e Administrador; gestão de usuários continua exclusiva do Administrador.
- Upload e consulta por equipamento cadastrado de FOTO (PNG/JPG, máximo 3 MB) e MANUAL (PDF, máximo 5 MB). Um arquivo por categoria por equipamento; novo upload substitui o arquivo daquela categoria. Armazenamento binário dentro do PostgreSQL.

## Instalação (Windows/WebStorm)
1. Faça uma cópia de segurança da pasta do projeto atual. Não substitua seu `.env` e não copie arquivos de configuração com segredos para outros computadores.
2. Substitua os arquivos de código do projeto pelos correspondentes deste pacote, preservando seu arquivo `backend/.env` atual apenas no seu computador. **Não substitua seu banco nem apague volumes Docker.**
3. Abra Docker Desktop. No diretório raiz, execute `docker compose up -d`.
4. Abra o terminal na pasta `backend` e execute `npm install` (caso necessário) e `npm run db:init`. Este comando roda `001_schema.sql` e depois `002_phase1.sql`; são comandos de criação/alteração idempotentes, sem DROP e sem limpar tabelas. **Não execute `npm run admin:create` se já tiver um administrador**.
5. Inicie backend: `node src/server.js`.
6. Em outro terminal, abra a pasta `frontend` e execute `npm install` (caso necessário) e `npm start`.
7. No navegador, acesse `http://localhost:4200`.

## Testes recomendados
- Login com administrador e com técnico.
- Cadastro de setor e vinculação ao cadastrar linha.
- Cadastro de máquina com comprimento em mm e posicionamento; conferir contagem e soma em Linhas SMT.
- Anexar PNG ou JPG à máquina já cadastrada; anexar PDF; consultar e baixar.
- Verificar que operador não consegue criar setores, linhas ou equipamentos; técnico não consegue cadastrar usuários.

## Observações
- Fotos e manuais estão nesta primeira versão na tabela `equipment_attachments`; mantenha backups do banco, pois os anexos também dependem dele.
- O totem ainda não usa a foto visualmente, e o cadastro de setores ainda não inclui edição/exclusão. Esses são aprimoramentos seguintes.
- Ainda não foram implementados Status de Linha, pendências, tempos avançados de OS ou Master List.
- Sintaxe do servidor conferida; compilação Angular e testes integrados dependem da instalação das dependências e execução em ambiente Windows com PostgreSQL. Esta versão é para testes, **não para produção**.
