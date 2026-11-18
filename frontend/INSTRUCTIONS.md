# MANTIS — frontend Angular

Esta pasta é a interface do MANTIS. HTML, CSS e JavaScript ficam aqui. O backend ativo é a API Django em `../backend`.

## Executar

1. Em outro terminal, abra `../backend` e execute `.\start.ps1`.
2. Nesta pasta, execute `npm ci` e `npm start`.
3. Abra **http://localhost:4200**.

`proxy.conf.json` encaminha as requisições `/api` para `http://127.0.0.1:8000`. A configuração antiga da porta 3000 foi substituída. Reinicie o servidor Angular após alterar o proxy.

Login usa matrícula e senha do banco Django. O token retornado pela API é enviado como Bearer nas requisições; o interceptor encerra a sessão local quando a API responde 401. Tokens emitidos pelo Express anterior exigem novo login.

## Compilar

```powershell
npm run build
```

Para publicar, sirva os arquivos de `dist/mantis/browser` em um servidor web com fallback para `index.html` nas rotas Angular. Encaminhe `/api` para o processo Django, na mesma origem. O Django não renderiza nem hospeda as telas.

As telas de peças e compras usam as rotas correspondentes na API Django. Fornecedores, clientes, tipos de ocorrência e tipos de OS permanecem em desenvolvimento. Veja `../README.md` e `../backend/README.md` para configuração do banco, permissões e limites.

## Cobertura e comentários no código

Na conferência de 24/10/2026, as 41 combinações de método HTTP e caminho encontradas nas chamadas do Angular possuem uma rota correspondente no Django. Essa conferência é de cobertura dos endereços; não comprova todos os comportamentos de ponta a ponta.

Pendência identificada: ao enviar uma compra com ficha incompleta, esta tela lê `error.missing` para apresentar uma lista detalhada de campos por peça. Atualmente o Django responde com `error`, contendo a mensagem geral, sem essa lista. O bloqueio de envio funciona, mas esse detalhe do contrato ainda precisa ser alinhado. E-mails também não são enviados pelo backend atual; o acompanhamento ocorre dentro do sistema.

Os comentários em português nos serviços, interceptor, rotas e componentes explicam o caminho dos dados e a responsabilidade de cada tela. No Django, as explicações correspondentes ficam em `maintenance/api.py`, `urls.py`, `services.py`, `forms.py`, `models.py` e `auth.py`. As proteções visuais do Angular não substituem as permissões conferidas na API.
