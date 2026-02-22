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

        vcenter_time = si.CurrentTime()
        start_time = vcenter_time - timedelta(days=2)

        time_filter = vim.event.EventFilterSpec.ByTime()
        time_filter.beginTime = start_time
        time_filter.endTime = vcenter_time

        filter_spec = vim.event.EventFilterSpec()
        filter_spec.time = time_filter

        # =====================================================================
        # SOLUÇÃO CONTRA O ERRO "ContentLibrary" E A PERDA DA TESTE-NSX6:
        # União Cirúrgica: Pedimos os eventos clássicos de VM e os novos de HA
        # =====================================================================
        
        # 1. Pega todos os eventos clássicos de VM (Seguro, não quebra o pyvmomi)
        filter_spec.type = [vim.event.VmEvent]
        
        # 2. Pega os eventos modernos explicitamente (Garante a teste-nsx3)
        filter_spec.eventTypeId = [
            "com.vmware.vc.ha.VmRestartedByHAEvent",
            "com.vmware.vc.ha.VmDasBeingResetEvent"
        ]

        event_manager = si.content.eventManager
        collector = event_manager.CreateCollectorForEvents(filter_spec)
        
        events = []
        while True:
            # Paginação de 500 em 500
            page = collector.ReadNextEvents(500)
            if not page:
                break
            events.extend(page)
            
        collector.DestroyCollector()

        ha_vms = []
        seen_vms = set() # Previne VMs duplicadas caso o vCenter registre dois logs iguais
        
        for event in events:
            msg = getattr(event, 'fullFormattedMessage', '')
            if not msg:
                msg = ''
                
            event_type_name = type(event).__name__
            event_type_id = getattr(event, 'eventTypeId', '')
            
            is_ha_restart = False
            
            # Valida todas as formas possíveis que o vCenter usa para avisar de HA
            if event_type_id == "com.vmware.vc.ha.VmRestartedByHAEvent":
                is_ha_restart = True
            elif "VmRestartedOnAlternateHostEvent" in event_type_name:
                is_ha_restart = True
            elif "VmDasBeingResetEvent" in event_type_name:
                is_ha_restart = True
            elif "vSphere HA restarted" in msg:
                is_ha_restart = True
                
            if is_ha_restart:
                if getattr(event, 'vm', None) and event.vm is not None:
                    vm_name = event.vm.name
                    
                    # Cria uma chave única por VM no mesmo minuto para evitar duplicidade
                    event_key = f"{vm_name}_{event.createdTime.strftime('%Y%m%d%H%M')}"
                    
                    if event_key not in seen_vms:
                        seen_vms.add(event_key)
                        ha_vms.append({
                            "vm_name": vm_name,
                            "data_evento": event.createdTime.strftime("%Y-%m-%d %H:%M:%S UTC"),
                            "mensagem": msg if msg else "vSphere HA restarted this virtual machine",
                            "tipo_evento": event_type_id if event_type_id else event_type_name
                        })

        print(json.dumps(ha_vms))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == '__main__':
    main()