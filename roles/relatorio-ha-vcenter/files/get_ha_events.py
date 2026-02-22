#!/usr/bin/env python3
import ssl
import sys
import os
import json
from datetime import timedelta
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
import atexit

def main():
    host = os.environ.get('VMWARE_HOST')
    user = os.environ.get('VMWARE_USER')
    password = os.environ.get('VMWARE_PASSWORD')

    if not all([host, user, password]):
        print(json.dumps({"error": "Variáveis de ambiente do vCenter ausentes"}))
        sys.exit(1)

    try:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        si = SmartConnect(host=host, user=user, pwd=password, sslContext=context)
        atexit.register(Disconnect, si)

        # Mesma lógica temporal: Get-Date e AddDays(-1)
        vcenter_time = si.CurrentTime()
        start_time = vcenter_time - timedelta(days=1)

        time_filter = vim.event.EventFilterSpec.ByTime()
        time_filter.beginTime = start_time
        time_filter.endTime = vcenter_time

        filter_spec = vim.event.EventFilterSpec()
        filter_spec.time = time_filter
        
        # 1. EVITA O "ContentLibrary" KEYERROR
        # Em vez de pedir tudo, pedimos apenas eventos relacionados a VMs e eventos "estendidos"
        # O EventEx engloba o "com.vmware.vc.ha.VmRestartedByHAEvent"
        filter_spec.type = [vim.event.VmEvent, vim.event.EventEx]

        # 2. EVITA BUSCA LENTA (Como o PowerCLI -Type Warning)
        # Trazemos apenas eventos de Alerta e Erro
        filter_spec.category = ["warning", "error"]

        event_manager = si.content.eventManager
        collector = event_manager.CreateCollectorForEvents(filter_spec)
        
        events = []
        while True:
            # Como filtramos pesado na origem, podemos ler em blocos maiores
            page = collector.ReadNextEvents(1000)
            if not page:
                break
            events.extend(page)
            
        collector.DestroyCollector()

        ha_vms = []
        seen_events = set() # Controle antiduplicidade
        
        for event in events:
            # Pega a mensagem formatada
            msg = getattr(event, 'fullFormattedMessage', '')
            if not msg:
                continue
                
            event_type_name = type(event).__name__
            event_type_id = getattr(event, 'eventTypeId', '')
                
            # Lógica inspirada no seu comando PowerCLI (Where {$_.FullFormattedMessage -match "restarted"})
            # Também procuramos pelos IDs padrões de HA conhecidos.
            is_ha = False
            if "restarted" in msg.lower() and "vSphere HA" in msg:
                is_ha = True
            elif event_type_id == "com.vmware.vc.ha.VmRestartedByHAEvent":
                is_ha = True
            elif "VmDasBeingResetEvent" in event_type_name:
                is_ha = True
                
            if is_ha:
                vm_name = "Desconhecida"
                # Verifica se o evento está atrelado a uma VM e pega o nome
                if getattr(event, 'vm', None) and event.vm is not None:
                    vm_name = event.vm.name
                    
                # Cria uma assinatura única para o evento (VM + Hora + Minuto + Segundo)
                # Assim garantimos que o mesmo evento não venha duplicado
                event_sig = f"{vm_name}_{event.createdTime.strftime('%Y%m%d%H%M%S')}"
                
                if event_sig not in seen_events:
                    seen_events.add(event_sig)
                    
                    ha_vms.append({
                        "vm_name": vm_name,
                        "data_evento": event.createdTime.strftime("%Y-%m-%d %H:%M:%S UTC"),
                        "mensagem": msg,
                        "tipo_evento": event_type_id if event_type_id else event_type_name
                    })

        # Retorna o array JSON limpo para o Ansible
        print(json.dumps(ha_vms))

    except Exception as e:
        # Importante: se houver um KeyError não mapeado (como ContentLibrary), ele não quebra silencioso
        print(json.dumps({"error": str(e), "type": type(e).__name__}))
        sys.exit(1)

if __name__ == '__main__':
    main()