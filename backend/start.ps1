# Atalho de preparação local: ambiente Python, dependências, PostgreSQL, migrações e API.
# -Preparar executa a preparação sem manter o servidor aberto. O Angular roda em outro terminal.
param([switch]$Preparar)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

# Interrompe a sequência se um programa externo falhar, para não continuar com preparação incompleta.
function Confirmar-Comando {
    if ($LASTEXITCODE -ne 0) { throw 'O comando anterior falhou. Confira a mensagem acima antes de continuar.' }
}

# No primeiro uso, cria configuração privada com valores aleatórios; nunca envie o .env ao Git.
$legacyConfig = -not (Test-Path -LiteralPath '.env') -and
    (Test-Path -LiteralPath '../.env') -and
    (Select-String -LiteralPath '../.env' -Pattern '^\s*BD_NOME\s*=' -Quiet)
if (-not $legacyConfig -and -not (Test-Path -LiteralPath '.env')) {
    $appSecret = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')
    $dbPassword = [guid]::NewGuid().ToString('N')
    $content = Get-Content -LiteralPath '.env.example' -Raw
    $content = $content.Replace('SUBSTITUA_POR_UM_SEGREDO_ALEATORIO_COM_64_CARACTERES', $appSecret)
    $content = $content.Replace('SUBSTITUA_POR_UMA_SENHA_FORTE', $dbPassword).Replace('SUA_SENHA', $dbPassword)
    [System.IO.File]::WriteAllText((Join-Path $PSScriptRoot '.env'), $content)
    Write-Host 'Configuração local criada com senhas aleatórias.'
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
if ($legacyConfig) {
    docker compose --env-file ../.env -f docker/compose.yml up -d --wait postgres
} else {
    docker compose up -d --wait postgres
}
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
