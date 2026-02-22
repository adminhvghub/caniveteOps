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

        time_filter = vim.event.EventFilterSpec.ByTime()
        time_filter.beginTime = start_time
        time_filter.endTime = vcenter_time

        event_manager = si.content.eventManager

        # 1. Pega todos os Clusters do vCenter
        container = si.content.viewManager.CreateContainerView(
            si.content.rootFolder,
            [vim.ClusterComputeResource],
            True
        )
        clusters = container.view

        ha_vms = []
        seen_events = set() # Evita VMs duplicadas através do ID único do evento

        # IDs exatos de eventos de HA
        ha_event_types = [
            "com.vmware.vc.ha.VmRestartedByHAEvent",
            "com.vmware.vc.ha.VmDasBeingResetEvent"
        ]

        # 2. Faz a busca separada, Cluster por Cluster (Dribla a omissão do vCenter)
        for cluster in clusters:
            filter_spec = vim.event.EventFilterSpec()
            filter_spec.time = time_filter
            filter_spec.eventTypeId = ha_event_types
            
            # Trava a busca especificamente neste cluster
            entity_filter = vim.event.EventFilterSpec.ByEntity()
            entity_filter.entity = cluster
            entity_filter.recursion = vim.event.EventFilterSpec.RecursionOption.all
            filter_spec.entity = entity_filter

            # Coletor local do cluster
            collector = event_manager.CreateCollectorForEvents(filter_spec)
            
            events = []
            while True:
                page = collector.ReadNextEvents(500)
                if not page:
                    break
                events.extend(page)
                
            collector.DestroyCollector()

            # 3. Processa os eventos encontrados neste cluster
            for event in events:
                if getattr(event, 'vm', None) and event.vm is not None:
                    vm_name = event.vm.name
                    event_id = event.key # A chave primária do banco de dados do vCenter
                    
                    if event_id not in seen_events:
                        seen_events.add(event_id)
                        
                        msg = getattr(event, 'fullFormattedMessage', '')
                        if not msg:
                            msg = "vSphere HA restarted this virtual machine"
                            
                        ha_vms.append({
                            "vm_name": vm_name,
                            "data_evento": event.createdTime.strftime("%Y-%m-%d %H:%M:%S UTC"),
                            "mensagem": msg,
                            "tipo_evento": getattr(event, 'eventTypeId', 'HA_Event')
                        })

        container.Destroy()
        
        # Devolve a lista completa e limpa para o Ansible
        print(json.dumps(ha_vms))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == '__main__':
    main()