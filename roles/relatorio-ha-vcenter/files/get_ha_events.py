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

        # Usa o relógio exato do vCenter
        vcenter_time = si.CurrentTime()
        # Ampliamos para 48h para evitar qualquer corte por fuso horário local vs UTC
        start_time = vcenter_time - timedelta(days=2)

        # 1. Filtro de tempo
        time_filter = vim.event.EventFilterSpec.ByTime()
        time_filter.beginTime = start_time
        time_filter.endTime = vcenter_time

        # 2. FILTRO NATIVO DO VCENTER (A Mágica acontece aqui)
        filter_spec = vim.event.EventFilterSpec()
        filter_spec.time = time_filter
        # Obriga o vCenter a processar e devolver APENAS este tipo de evento
        filter_spec.eventTypeId = ["com.vmware.vc.ha.VmRestartedByHAEvent"]

        event_manager = si.content.eventManager
        
        # Coleta os eventos já filtrados na origem
        events = event_manager.QueryEvents(filter_spec)

        ha_vms = []
        
        for event in events:
            # Pega a mensagem formatada, se não existir, usa uma padrão
            msg = getattr(event, 'fullFormattedMessage', '')
            if not msg:
                msg = "vSphere HA restarted this virtual machine"
                
            vm_name = "Desconhecida"
            if getattr(event, 'vm', None) and event.vm is not None:
                vm_name = event.vm.name
            
            ha_vms.append({
                "vm_name": vm_name,
                "data_evento": event.createdTime.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "mensagem": msg,
                "tipo_evento": "com.vmware.vc.ha.VmRestartedByHAEvent"
            })

        # Imprime o resultado como JSON para o Ansible
        print(json.dumps(ha_vms))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == '__main__':
    main()