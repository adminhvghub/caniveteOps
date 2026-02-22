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
        start_time = vcenter_time - timedelta(days=1)

        event_manager = si.content.eventManager
        
        time_filter = vim.event.EventFilterSpec.ByTime()
        time_filter.beginTime = start_time
        time_filter.endTime = vcenter_time

        filter_spec = vim.event.EventFilterSpec(time=time_filter)

        events = event_manager.QueryEvents(filter_spec)

        diagnostic_events = []
        
        for event in events:
            # Pegar a mensagem formatada (pode ser vazia)
            msg = getattr(event, 'fullFormattedMessage', '')
            
            # Identificar o tipo exato da classe do evento
            event_class = type(event).__name__
            
            # Se for EventEx, tem um ID específico (como aquele que você achou antes)
            event_type_id = getattr(event, 'eventTypeId', 'N/A')

            # Palavras-chave amplas para tentar capturar o restart
            keywords = ["HA", "High Availability", "Restart", "Power On", "PowerOn", "Reset", "Failover"]
            
            # Verifica se alguma palavra-chave está na mensagem ou no ID do evento
            is_relevant = any(kw.lower() in msg.lower() for kw in keywords) or \
                          any(kw.lower() in event_type_id.lower() for kw in keywords) or \
                          any(kw.lower() in event_class.lower() for kw in keywords)

            if is_relevant:
                vm_name = "Desconhecida"
                if getattr(event, 'vm', None) and event.vm is not None:
                    vm_name = event.vm.name
                
                # Ignorar eventos de heartbeat de datastore para limpar a saída
                if "heartbeat datastores" not in msg:
                    diagnostic_events.append({
                        "vm_name": vm_name,
                        "data_evento": event.createdTime.strftime("%Y-%m-%d %H:%M:%S UTC"),
                        "mensagem": msg,
                        "classe_evento": event_class,
                        "id_evento_ex": event_type_id
                    })

        print(json.dumps(diagnostic_events))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == '__main__':
    main()