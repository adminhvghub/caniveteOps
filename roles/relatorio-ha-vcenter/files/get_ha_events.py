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
        print(json.dumps({"error": "Variáveis de ambiente ausentes"}))
        sys.exit(1)

    try:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        si = SmartConnect(host=host, user=user, pwd=password, sslContext=context)
        atexit.register(Disconnect, si)

        # Volta 2 dias para ter certeza absoluta que o evento está na janela
        vcenter_time = si.CurrentTime()
        start_time = vcenter_time - timedelta(days=2)

        time_filter = vim.event.EventFilterSpec.ByTime()
        time_filter.beginTime = start_time
        time_filter.endTime = vcenter_time

        filter_spec = vim.event.EventFilterSpec()
        filter_spec.time = time_filter
        
        # Copiamos a lógica do seu PowerCLI (-Type Warning)
        filter_spec.category = ["warning"]

        event_manager = si.content.eventManager
        collector = event_manager.CreateCollectorForEvents(filter_spec)
        
        events = []
        try:
            while True:
                # Lendo de 500 em 500
                page = collector.ReadNextEvents(500)
                if not page:
                    break
                events.extend(page)
        except Exception as e:
            # Se a API do VMware mandar um lixo que o pyvmomi não entenda, 
            # nós ignoramos o erro e continuamos com os eventos que já lemos!
            pass
            
        collector.DestroyCollector()

        dump_eventos = []
        
        for event in events:
            msg = getattr(event, 'fullFormattedMessage', '')
            if not msg:
                continue
                
            # Lógica crua do seu PowerCLI: Where {$_.FullFormattedMessage -match "restarted"}
            if "restarted" in msg.lower():
                
                vm_name = "Desconhecida"
                if getattr(event, 'vm', None) and event.vm is not None:
                    vm_name = event.vm.name

                event_class = type(event).__name__
                event_type_id = getattr(event, 'eventTypeId', 'N/A')

                dump_eventos.append({
                    "vm_name": vm_name,
                    "data_evento": event.createdTime.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "mensagem": msg,
                    "tipo_evento": f"Classe: {event_class} | ID: {event_type_id}"
                })

        # Retorna a lista para o Ansible
        print(json.dumps(dump_eventos))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == '__main__':
    main()