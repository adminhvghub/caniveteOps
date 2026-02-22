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
        # Ignora avisos de certificado (padrão em automação VMware)
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        si = SmartConnect(host=host, user=user, pwd=password, sslContext=context)
        atexit.register(Disconnect, si)

        # 1. Lógica PowerCLI: -Start (Get-Date).AddDays(-1)
        vcenter_time = si.CurrentTime()
        start_time = vcenter_time - timedelta(days=1)

        time_filter = vim.event.EventFilterSpec.ByTime()
        time_filter.beginTime = start_time

        filter_spec = vim.event.EventFilterSpec()
        filter_spec.time = time_filter
        
        # 2. Lógica PowerCLI: -Type Warning
        # Ao pedir APENAS "warning", o vCenter não nos envia os eventos de "ContentLibrary" (que são "info")
        # Isso resolve o bug da biblioteca pyvmomi nativamente.
        filter_spec.category = ["warning"]

        event_manager = si.content.eventManager
        
        # O Collector é o equivalente do PowerCLI para suportar o "-MaxSamples 100000"
        collector = event_manager.CreateCollectorForEvents(filter_spec)
        
        events = []
        while True:
            page = collector.ReadNextEvents(1000)
            if not page:
                break
            events.extend(page)
            
        collector.DestroyCollector()

        ha_vms = []
        
        for event in events:
            msg = getattr(event, 'fullFormattedMessage', '')
            if not msg:
                continue
                
            # 3. Lógica PowerCLI: Where {$_.FullFormattedMessage -match "restarted"}
            # E garantimos que o texto tenha "vSphere HA" para não pegar reinícios manuais
            if "restarted" in msg.lower() and "vSphere HA" in msg:
                
                vm_name = "Desconhecida"
                # Lógica PowerCLI: Se ($evento.Vm) { $evento.Vm.Name }
                if getattr(event, 'vm', None) and event.vm is not None:
                    vm_name = event.vm.name
                    
                ha_vms.append({
                    "vm_name": vm_name,
                    "data_evento": event.createdTime.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "mensagem": msg,
                    "tipo_evento": getattr(event, 'eventTypeId', type(event).__name__)
                })

        # Imprime o JSON limpo para o AWX
        print(json.dumps(ha_vms))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == '__main__':
    main()