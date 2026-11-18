# Verificação — arquitetura Angular + API Django — 24/10/2026

A implementação ativa usa Angular para todas as telas e Django somente como API. As verificações abaixo substituem as verificações anteriores de páginas renderizadas pelo Django.

## Executado nesta alteração

- Removidos `maintenance/templates`, `maintenance/static`, `staticfiles` e as views que renderizavam páginas Django.
- Removida a configuração de templates, sessões de navegador, arquivos estáticos, WhiteNoise e `collectstatic` do backend e de seu inicializador/Dockerfile.
- Proxy Angular configurado para `/api` em `http://127.0.0.1:8000`.
- Implementados os contratos da interface Angular para login, usuários, setores, linhas, equipamentos, anexos, movimentos, OS, peças, fichas técnicas e compras.
- Tokens Bearer assinados, com expiração, verificação de conta ativa e invalidação após redefinição de senha. Respostas 401 encerram a sessão local no Angular.
- Atualização das telas Angular após conclusão/erro das requisições, usando `ChangeDetectorRef.markForCheck()` sem alterar o layout.
- **21 testes aprovados no PostgreSQL 17**, incluindo migrações, autenticação bcrypt legada, permissões, isolamento do operador, cadastros, anexos, OS, compras, snapshot, CSV e concorrência de alocação. A limpeza do banco de teste também concluiu sem erros.
- Teste isolado SQLite: **20 aprovados e 1 pulado** (concorrência exige PostgreSQL).
- `makemigrations --check --dry-run`: nenhuma migração nova necessária.
- Compilação Angular concluída.
- Conferência real no navegador: login no Angular, cadastro de setor e peça, carregamento de gestores e criação de rascunho de compra pela API Django.
- Requisição HTTP por intermédio do proxy Angular para `/api/health` confirmou o serviço Django.

O PostgreSQL de validação foi criado em um contêiner exclusivo e temporário, removido ao final. A conferência visual usou SQLite em memória e contas/dados fictícios. Nenhum banco do usuário, `.env` ou volume existente foi modificado. Os servidores e arquivos temporários de validação foram encerrados/removidos ao final.

## Ainda depende do ambiente de destino

- Primeiro início com `.\start.ps1`, configuração local e criação do administrador pelo responsável.
- Construção/execução da imagem Docker da API no ambiente de destino.
- Validação de um backup real antes de adotar o banco da implementação Express anterior.
- Configuração de HTTPS, hospedagem do build Angular e proxy `/api` para publicação.

As funcionalidades em desenvolvimento e os limites operacionais estão nos READMEs.

## Conferência de contratos e documentação do código — 24/10/2026

- As 41 combinações de método HTTP e caminho encontradas nas chamadas do Angular resolvem para rotas Django que aceitam o método correspondente. Parâmetros dinâmicos foram normalizados para conferir o roteamento; essa checagem não substitui a validação de seus valores ou a execução de cada fluxo no navegador.
- A cobertura de rotas não significa compatibilidade comportamental de 100%. Foi identificada uma diferença: o tratamento de ficha incompleta da tela de compras espera `error.missing`, enquanto `submit_purchase` ainda responde apenas com `error`. O bloqueio permanece, mas não há lista estruturada dos campos pendentes por peça.
- Os retornos de notificação não representam envio de e-mail. Não existe integração externa de envio neste backend.
- Incluídos comentários e docstrings em português explicando autenticação, contratos, telas, validação, persistência, permissões e transações. As inclusões de documentação preservam a lógica existente; a pendência acima está marcada com TODO nos dois lados.
