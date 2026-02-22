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

        # Filtro pedindo APENAS pelo tempo (todas as categorias, todos os tipos)
        time_filter = vim.event.EventFilterSpec.ByTime()
        time_filter.beginTime = start_time
        time_filter.endTime = vcenter_time

        filter_spec = vim.event.EventFilterSpec()
        filter_spec.time = time_filter

        event_manager = si.content.eventManager
        collector = event_manager.CreateCollectorForEvents(filter_spec)
        
        events = []
        while True:
            # Baixa de 500 em 500 para não estourar o limite do SOAP da VMware
            page = collector.ReadNextEvents(500)
            if not page:
                break
            events.extend(page)
            
        collector.DestroyCollector()

        ha_vms = []
        
        # Filtro Fino Feito 100% no Python (Ignora os bugs de busca do vCenter)
        for event in events:
            msg = getattr(event, 'fullFormattedMessage', '')
            if not msg:
                msg = ''
                
            event_type_name = type(event).__name__
            event_type_id = getattr(event, 'eventTypeId', '')
            
            is_ha_restart = False
            
            # Checa todas as possibilidades de ser um evento de HA
            if event_type_id == "com.vmware.vc.ha.VmRestartedByHAEvent":
                is_ha_restart = True
            elif "VmRestartedOnAlternateHostEvent" in event_type_name:
                is_ha_restart = True
            elif "VmDasBeingResetEvent" in event_type_name:
                is_ha_restart = True
            elif "vSphere HA restarted virtual machine" in msg:
                is_ha_restart = True
                
            # Se for HA, garante que temos a VM afetada
            if is_ha_restart:
                if getattr(event, 'vm', None) and event.vm is not None:
                    vm_name = event.vm.name
                    
                    ha_vms.append({
                        "vm_name": vm_name,
                        "data_evento": event.createdTime.strftime("%Y-%m-%d %H:%M:%S UTC"),
                        "mensagem": msg,
                        "tipo_evento": event_type_id if event_type_id else event_type_name
                    })

        # Retorna a lista final para o Ansible
        print(json.dumps(ha_vms))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == '__main__':
    main()