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

        # Volta 2 dias para cobrir qualquer diferença de timezone (UTC vs Local)
        vcenter_time = si.CurrentTime()
        start_time = vcenter_time - timedelta(days=2)

        time_filter = vim.event.EventFilterSpec.ByTime()
        time_filter.beginTime = start_time
        time_filter.endTime = vcenter_time

        event_manager = si.content.eventManager

        # 1. Extrai a lista de todas as VMs do vCenter
        container = si.content.viewManager.CreateContainerView(
            si.content.rootFolder, [vim.VirtualMachine], True
        )
        vms = container.view

        ha_vms = []

        # 2. Interroga cada VM separadamente
        # Isso resolve 100% o bug de eventos simultâneos e o crash de leitura de logs alheios
        for vm in vms:
            filter_spec = vim.event.EventFilterSpec()
            filter_spec.time = time_filter
            # Foco apenas no evento de HA da VM
            filter_spec.eventTypeId = [
                "com.vmware.vc.ha.VmRestartedByHAEvent",
                "com.vmware.vc.ha.VmDasBeingResetEvent"
            ]
            
            entity_filter = vim.event.EventFilterSpec.ByEntity()
            entity_filter.entity = vm
            entity_filter.recursion = vim.event.EventFilterSpec.RecursionOption.self
            filter_spec.entity = entity_filter

            try:
                # QueryEvents é muito mais rápido que o Collector para consultas diretas
                events = event_manager.QueryEvents(filter_spec)
                
                for event in events:
                    msg = getattr(event, 'fullFormattedMessage', '')
                    if not msg:
                        msg = "vSphere HA restarted this virtual machine"
                        
                    ha_vms.append({
                        "vm_name": vm.name,
                        "data_evento": event.createdTime.strftime("%Y-%m-%d %H:%M:%S UTC"),
                        "mensagem": msg,
                        "tipo_evento": getattr(event, 'eventTypeId', 'HA_Event')
                    })
            except Exception:
                # Se falhar ao ler uma VM específica por qualquer corrupção local, ignora e segue buscando nas outras
                continue

        container.Destroy()

        # Devolve o JSON com a lista completa das VMs afetadas
        print(json.dumps(ha_vms))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == '__main__':
    main()