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
        # Ignora erros de certificado SSL (útil para labs/PoC)
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        # Conecta ao vCenter
        si = SmartConnect(host=host, user=user, pwd=password, sslContext=context)
        atexit.register(Disconnect, si)

        # Usa o relógio exato do vCenter para evitar bugs de Timezone
        vcenter_time = si.CurrentTime()
        start_time = vcenter_time - timedelta(days=1) # Janela de 24 horas

        event_manager = si.content.eventManager
        
        # Cria o filtro de tempo
        time_filter = vim.event.EventFilterSpec.ByTime()
        time_filter.beginTime = start_time
        time_filter.endTime = vcenter_time

        filter_spec = vim.event.EventFilterSpec(time=time_filter)

        # Coleta os eventos
        events = event_manager.QueryEvents(filter_spec)

        ha_vms = []
        
        for event in events:
            msg = getattr(event, 'fullFormattedMessage', '')
            event_type = type(event).__name__
            
            # Filtro para encontrar os eventos de HA (DAS)
            is_ha_event = False
            if msg and ("vSphere HA" in msg or "High Availability" in msg):
                is_ha_event = True
            elif "Das" in event_type or "HAEvent" in event_type:
                is_ha_event = True

            if is_ha_event:
                vm_name = "Desconhecida"
                if getattr(event, 'vm', None) and event.vm is not None:
                    vm_name = event.vm.name
                
                ha_vms.append({
                    "vm_name": vm_name,
                    "data_evento": event.createdTime.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "mensagem": msg,
                    "tipo_evento": event_type
                })

        # Imprime o resultado como JSON para o Ansible capturar
        print(json.dumps(ha_vms))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == '__main__':
    main()