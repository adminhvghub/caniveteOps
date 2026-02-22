#!/usr/bin/env python3
import atexit
import ssl
import os
import json
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim

def get_ha_events():
    host = os.environ.get('VMWARE_HOST')
    user = os.environ.get('VMWARE_USER')
    pwd = os.environ.get('VMWARE_PASSWORD')

    # Ignora erro de certificado SSL
    context = ssl._create_unverified_context()

    try:
        si = SmartConnect(host=host, user=user, pwd=pwd, sslContext=context)
        atexit.register(Disconnect, si)
        
        event_manager = si.content.eventManager
        
        # Filtra especificamente por eventos de HA
        filter_spec = vim.event.EventFilterSpec()
        filter_spec.eventTypeId = [
            "VmRestartedOnAlternateHostEvent",
            "VmDasBeingResetEvent"
        ]
        
        # Coleta os eventos
        events = event_manager.QueryEvents(filter_spec)
        
        ha_vms = []
        for event in events:
            ha_vms.append({
                "vm_name": event.vm.name if event.vm else "Desconhecida",
                "data_evento": event.createdTime.strftime("%Y-%m-%d %H:%M:%S"),
                "mensagem": event.fullFormattedMessage
            })
            
        print(json.dumps(ha_vms))

    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    get_ha_events()