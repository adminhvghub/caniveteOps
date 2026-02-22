#!/usr/bin/env pwsh
$ErrorActionPreference = "Stop"

$viServer = $env:VMWARE_HOST
$viUser = $env:VMWARE_USER
$viPassword = $env:VMWARE_PASSWORD

if (-not $viServer -or -not $viUser -or -not $viPassword) {
    Write-Output (ConvertTo-Json @{error="Variáveis de ambiente do vCenter ausentes"})
    exit 1
}

try {
    # Suprime avisos de certificado e telemetria para não sujar o output JSON
    Set-PowerCLIConfiguration -InvalidCertificateAction Ignore -ParticipateInCEIP $false -Confirm:$false -Scope Session -WarningAction SilentlyContinue -InformationAction SilentlyContinue | Out-Null

    # Conecta ao vCenter
    Connect-VIServer -Server $viServer -User $viUser -Password $viPassword -WarningAction SilentlyContinue -InformationAction SilentlyContinue | Out-Null

    # O SEU COMANDO EXATO AQUI (com janela de 2 dias para garantir fuso horário)
    $startDate = (Get-Date).AddDays(-2)
    $events = Get-VIEvent -MaxSamples 100000 -Start $startDate -Type Warning | Where-Object { $_.FullFormattedMessage -match "restarted" }

    $ha_vms = @()

    if ($events) {
        foreach ($event in $events) {
            # Extrai o nome da VM (usando o objeto Vm ou via Regex no texto)
            $vmName = "Desconhecida"
            if ($event.Vm -and $event.Vm.Name) {
                $vmName = $event.Vm.Name
            } elseif ($event.FullFormattedMessage -match "virtual machine (.+?) on host") {
                $vmName = $matches[1]
            }

            $ha_vms += @{
                vm_name     = $vmName
                data_evento = $event.CreatedTime.ToString("yyyy-MM-dd HH:mm:ss")
                mensagem    = $event.FullFormattedMessage
                tipo_evento = $event.GetType().Name
            }
        }
    }

    # Desconecta
    Disconnect-VIServer -Server $viServer -Confirm:$false -Force | Out-Null

    # Retorna o JSON limpo
    Write-Output ($ha_vms | ConvertTo-Json -Compress)

} catch {
    Write-Output (ConvertTo-Json @{error=$_.Exception.Message})
    exit 1
}