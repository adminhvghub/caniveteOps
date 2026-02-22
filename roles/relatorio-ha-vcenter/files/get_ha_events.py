#!/usr/bin/env python3
import ssl
import sys
import os
import json
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

        event_manager = si.content.eventManager

        # Filtro cru: Apenas Warnings e Errors (evita o crash do ContentLibrary)
        filter_spec = vim.event.EventFilterSpec()
        filter_spec.category = ["warning", "error"]

        collector = event_manager.CreateCollectorForEvents(filter_spec)
        
        # Puxa os últimos 500 eventos de forma bruta
        events = collector.ReadNextEvents(500)
        collector.DestroyCollector()

        dump_eventos = []
        
        for event in events:
            msg = getattr(event, 'fullFormattedMessage', 'Sem mensagem')
            event_class = type(event).__name__
            event_type_id = getattr(event, 'eventTypeId', 'N/A')
            
            vm_name = "N/A"
            if getattr(event, 'vm', None) and event.vm is not None:
                vm_name = event.vm.name

            dump_eventos.append({
                "Classe_Python": event_class,
                "ID_Interno": event_type_id,
                "Data_Criacao": event.createdTime.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "VM_Afetada": vm_name,
                "Mensagem": msg
            })

        # Retorna a lista crua para o Ansible
        print(json.dumps(dump_eventos))

    except Exception as e:
        print(json.dumps({"error": str(e), "tipo_erro": type(e).__name__}))
        sys.exit(1)

if __name__ == '__main__':
    main()