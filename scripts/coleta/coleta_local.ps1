# Coleta local do Agendão Curitiba, sem Claude (Agendador de Tarefas do Windows, 21h).
# Atualiza o clone, roda run_local.py (abre uma janela de navegador por alguns minutos)
# e envia os arquivos brutos para o branch coleta-bruta (um commit só, substituído a cada noite).
# A rotina na nuvem pega esse branch às 6h e faz o resto.
$ErrorActionPreference = 'Stop'
$repo = Resolve-Path (Join-Path $PSScriptRoot '..\..')
Set-Location $repo
New-Item -ItemType Directory -Force work | Out-Null
Start-Transcript -Path (Join-Path $repo 'work\coleta_local.log') -Force | Out-Null
try {
    git fetch -q origin main
    git reset -q --hard origin/main
    $py = Join-Path $repo '.venv\Scripts\python.exe'
    $raw = Join-Path $repo 'work\raw'
    if (Test-Path $raw) { Remove-Item -Recurse -Force $raw }
    $hoje = Get-Date -Format 'yyyy-MM-dd'
    & $py -X utf8 scripts\coleta\run_local.py $raw
    if ($LASTEXITCODE -ne 0) { throw "run_local.py saiu com código $LASTEXITCODE" }

    # Commit órfão com os brutos, empurrado com --force para coleta-bruta (o main não é tocado).
    $tmp = Join-Path $repo 'work\bruta'
    if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
    New-Item -ItemType Directory $tmp | Out-Null
    Copy-Item (Join-Path $raw '*.json') $tmp
    $meta = @{ data = $hoje; at = (Get-Date).ToUniversalTime().ToString('o'); commitMain = (git rev-parse HEAD) } | ConvertTo-Json
    [IO.File]::WriteAllText((Join-Path $tmp 'meta.json'), $meta)
    $url = git remote get-url origin
    Push-Location $tmp
    git init -q -b coleta-bruta
    git add -A
    git -c user.name='Coleta local (PC)' -c user.email='noreply@anthropic.com' commit -q -m "Coleta bruta de $hoje"
    $ok = $false
    foreach ($espera in 0, 2, 4, 8, 16) {
        Start-Sleep -Seconds $espera
        git push -q --force $url coleta-bruta:coleta-bruta
        if ($LASTEXITCODE -eq 0) { $ok = $true; break }
    }
    Pop-Location
    if (-not $ok) { throw 'push para coleta-bruta falhou' }
    Write-Output "Coleta bruta de $hoje enviada."
} finally {
    Stop-Transcript | Out-Null
}
