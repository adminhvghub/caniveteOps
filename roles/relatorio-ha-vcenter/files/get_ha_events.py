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

        # Mesma lógica do PowerCLI: Get-Date e AddDays(-1)
        vcenter_time = si.CurrentTime()
        start_time = vcenter_time - timedelta(days=1)

        time_filter = vim.event.EventFilterSpec.ByTime()
        time_filter.beginTime = start_time
        time_filter.endTime = vcenter_time

        filter_spec = vim.event.EventFilterSpec()
        filter_spec.time = time_filter
        # Simula o '-Type Warning' do PowerCLI
        filter_spec.type = [vim.event.WarningEvent]

        event_manager = si.content.eventManager
        collector = event_manager.CreateCollectorForEvents(filter_spec)
        
        events = []
        while True:
            page = collector.ReadNextEvents(1000) # Equivalente ao -MaxSamples
            if not page:
                break
            events.extend(page)
            
        collector.DestroyCollector()

        ha_vms = []
        
        for event in events:
            # Pega a mensagem formatada
            msg = getattr(event, 'fullFormattedMessage', '')
            if not msg:
                continue
                
            # Lógica exata do seu comando PowerCLI: Where {$_.FullFormattedMessage -match "restarted"}
            if "restarted" in msg.lower() and "vSphere HA" in msg:
                
                vm_name = "Desconhecida"
                if getattr(event, 'vm', None) and event.vm is not None:
                    vm_name = event.vm.name
                    
                ha_vms.append({
                    "vm_name": vm_name,
                    "data_evento": event.createdTime.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "mensagem": msg,
                    "tipo_evento": type(event).__name__
                })

        # Retorna o array JSON para o Ansible
        print(json.dumps(ha_vms))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == '__main__':
    main()