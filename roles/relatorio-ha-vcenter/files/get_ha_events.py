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
        # Ignora avisos de certificado
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        si = SmartConnect(host=host, user=user, pwd=password, sslContext=context)
        atexit.register(Disconnect, si)

        # Equivalente ao (Get-Date).AddDays(-1)
        vcenter_time = si.CurrentTime()
        start_time = vcenter_time - timedelta(days=1)

        time_filter = vim.event.EventFilterSpec.ByTime()
        time_filter.beginTime = start_time
        time_filter.endTime = vcenter_time

        # Montando o filtro baseado no aprendizado do artigo e do PowerCLI
        filter_spec = vim.event.EventFilterSpec()
        filter_spec.time = time_filter
        
        # AQUI ESTÁ A CHAVE: Isso equivale ao '-Type Warning' do PowerCLI
        filter_spec.category = ["warning"]

        # Usando o Collector corretamente
        event_manager = si.content.eventManager
        collector = event_manager.CreateCollectorForEvents(filter_spec)
        
        events = []
        while True:
            # Paginação (Equivalente ao -MaxSamples)
            page = collector.ReadNextEvents(1000)
            if not page:
                break
            events.extend(page)
            
        collector.DestroyCollector()

        ha_vms = []
        
        # Iterando e filtrando as mensagens
        for event in events:
            msg = getattr(event, 'fullFormattedMessage', '')
            if not msg:
                continue
                
            # AQUI ESTÁ A CHAVE 2: Equivalente ao Where {$_.FullFormattedMessage -match "restarted"}
            if "restarted" in msg.lower() and "vsphere ha" in msg.lower():
                
                vm_name = "Desconhecida"
                if getattr(event, 'vm', None) and event.vm is not None:
                    vm_name = event.vm.name
                    
                ha_vms.append({
                    "vm_name": vm_name,
                    "data_evento": event.createdTime.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "mensagem": msg,
                    "tipo_evento": getattr(event, 'eventTypeId', type(event).__name__)
                })

        # Retorna o resultado json para o Ansible
        print(json.dumps(ha_vms))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == '__main__':
    main()