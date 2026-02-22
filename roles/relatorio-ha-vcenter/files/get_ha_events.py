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

        # Usa o relógio exato do vCenter para a janela de 24h
        vcenter_time = si.CurrentTime()
        start_time = vcenter_time - timedelta(days=1)

        event_manager = si.content.eventManager
        
        # Filtro de tempo
        time_filter = vim.event.EventFilterSpec.ByTime()
        time_filter.beginTime = start_time
        time_filter.endTime = vcenter_time

        filter_spec = vim.event.EventFilterSpec(time=time_filter)

        # Buscar todos os eventos no período
        events = event_manager.QueryEvents(filter_spec)

        ha_vms = []
        
        for event in events:
            # Verifica se o evento é um EventEx
            if isinstance(event, vim.event.EventEx):
                # Pega o ID específico do evento de HA
                event_type_id = getattr(event, 'eventTypeId', '')
                
                # Se for o evento exato de restart por HA
                if event_type_id == "com.vmware.vc.ha.VmRestartedByHAEvent":
                    
                    msg = getattr(event, 'fullFormattedMessage', 'VM Restarted by vSphere HA')
                    
                    vm_name = "Desconhecida"
                    # No EventEx, a VM afetada está atrelada à propriedade 'vm' do evento
                    if getattr(event, 'vm', None) and event.vm is not None:
                        vm_name = event.vm.name
                    
                    ha_vms.append({
                        "vm_name": vm_name,
                        "data_evento": event.createdTime.strftime("%Y-%m-%d %H:%M:%S UTC"),
                        "mensagem": msg,
                        "tipo_evento": event_type_id
                    })

        # Retorna o JSON para o Ansible
        print(json.dumps(ha_vms))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == '__main__':
    main()