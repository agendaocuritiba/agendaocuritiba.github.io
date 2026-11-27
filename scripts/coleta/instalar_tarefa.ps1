# Cria (ou recria) a tarefa "Agendao coleta 21h" no Agendador de Tarefas do Windows.
# Roda coleta_local.ps1 todo dia às 21h; se o PC estiver desligado nessa hora, roda assim que possível.
# Só roda com o usuário logado, porque abre uma janela de navegador (o guia da Prefeitura recusa o modo sem janela).
$ps1 = Join-Path $PSScriptRoot 'coleta_local.ps1'
$repo = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$a = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Minimized -File `"$ps1`"" -WorkingDirectory $repo
$t = New-ScheduledTaskTrigger -Daily -At '21:00'
$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1) -MultipleInstances IgnoreNew
$p = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName 'Agendao coleta 21h' -Description 'Agendao Curitiba: le os 12 sites sem Claude e envia ao branch coleta-bruta; a rotina na nuvem processa as 6h.' -Action $a -Trigger $t -Settings $s -Principal $p -Force | Out-Null
"Tarefa criada. Proxima execucao: " + (Get-ScheduledTask 'Agendao coleta 21h' | Get-ScheduledTaskInfo).NextRunTime
