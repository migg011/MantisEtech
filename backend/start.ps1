# Atalho de preparação local: ambiente Python, dependências, PostgreSQL, migrações e API.
# -Preparar executa a preparação sem manter o servidor aberto. O Angular roda em outro terminal.
param([switch]$Preparar)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

# Interrompe a sequência se um programa externo falhar, para não continuar com preparação incompleta.
function Confirmar-Comando {
    if ($LASTEXITCODE -ne 0) { throw 'O comando anterior falhou. Confira a mensagem acima antes de continuar.' }
}

# No primeiro uso, cria configuração privada na RAIZ do projeto (compartilhada pelo Django e Docker).
$projectRoot = Split-Path $PSScriptRoot -Parent
$envPath = Join-Path $projectRoot '.env'
$examplePath = Join-Path $projectRoot '.env.example'

if (-not (Test-Path -LiteralPath $envPath)) {
    if (-not (Test-Path -LiteralPath $examplePath)) {
        @"
BD_NOME=mantis
BD_USUARIO=mantis
BD_SENHA=SUBSTITUA_POR_UMA_SENHA_FORTE
BD_HOST=127.0.0.1
BD_PORT=5433
DJANGO_SECRET_KEY=SUBSTITUA_POR_UM_SEGREDO_ALEATORIO_COM_64_CARACTERES
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

"@ | Set-Content -Path $examplePath -Encoding UTF8
    }
    $appSecret = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')
    $dbPassword = [guid]::NewGuid().ToString('N')
    $content = Get-Content -LiteralPath $examplePath -Raw
    $content = $content.Replace('SUBSTITUA_POR_UM_SEGREDO_ALEATORIO_COM_64_CARACTERES', $appSecret).Replace('SUBSTITUA_POR_UM_SEGREDO_ALEATORIO', $appSecret)
    $content = $content.Replace('SUBSTITUA_POR_UMA_SENHA_FORTE', $dbPassword).Replace('SUA_SENHA', $dbPassword)
    [System.IO.File]::WriteAllText($envPath, $content)
    Write-Host "Configuração local criada em $envPath com senhas aleatórias."
}

$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    $pyCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCommand) { & $pyCommand.Source -3 -m venv .venv }
    elseif ($pythonCommand) { & $pythonCommand.Source -m venv .venv }
    else { throw 'Instale Python 3.12 ou superior e execute novamente.' }
    Confirmar-Comando
}

# Cada comando prepara uma camada: pacotes Python -> banco disponível -> tabelas -> conta inicial.
& $pythonPath -m pip install -r requirements.lock.txt
Confirmar-Comando
# O Compose fica em docker; as variáveis vêm do .env da raiz.
docker compose --env-file "$envPath" -f docker/compose.yml up -d --wait postgres
Confirmar-Comando
& $pythonPath manage.py migrate --noinput
Confirmar-Comando
& $pythonPath manage.py shell -c "from maintenance.models import User; import sys; sys.exit(0 if User.objects.filter(role='ADMINISTRADOR',active=True).exists() else 7)"
if ($LASTEXITCODE -eq 7) {
    & $pythonPath manage.py create_admin
    Confirmar-Comando
} elseif ($LASTEXITCODE -ne 0) { throw 'Não foi possível verificar o administrador.' }
if (-not $Preparar) {
    Write-Host 'API Django: http://127.0.0.1:8000/api/health'
    Write-Host 'Em outro terminal, execute npm start na pasta ../frontend e abra http://localhost:4200.'
    Write-Host 'Para encerrar a API, pressione Ctrl+C.'
    & $pythonPath manage.py runserver 127.0.0.1:8000
}
