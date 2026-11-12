# Docker do Mantis

Execute os comandos abaixo na raiz do projeto.

## PostgreSQL local

```powershell
docker compose --env-file .env -f backend/docker/compose.yml up -d --wait postgres
```

O Compose usa as variáveis BD_* do único `.env`, na raiz. O nome do projeto
continua `projeto-mantis`, preservando a identificação do volume existente.

## Imagem da API

```powershell
docker build -f backend/docker/Dockerfile -t mantis-api backend
```

O contexto de build é `backend`, por isso `.dockerignore` permanece nessa pasta.
O Compose atual inicia somente o PostgreSQL. A API e o Angular são iniciados
localmente conforme o README do backend.

### Proteções do painel e arquivos estáticos

O Admin impede que o usuário conectado desative a própria conta ou retire seu
perfil de administrador. Operadores só podem ser vinculados a linhas ativas.

A imagem Docker executa `collectstatic` durante o build e serve os arquivos do
Admin com WhiteNoise, inclusive com `DEBUG=False`. As variáveis usadas apenas
na coleta são valores fictícios de build, sem acesso ao banco ou ao `.env`.
Referência: https://whitenoise.readthedocs.io/en/stable/django.html
