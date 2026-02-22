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
        print(json.dumps([{"vm_name": "ERRO", "data_evento": "N/A", "mensagem": "Variáveis de ambiente ausentes", "tipo_evento": "Erro"}]))
        sys.exit(0)

    try:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        si = SmartConnect(host=host, user=user, pwd=password, sslContext=context)
        atexit.register(Disconnect, si)

        event_manager = si.content.eventManager
        
        # 1. FILTRO 100% VAZIO: Traz tudo sem distinção de data, tipo ou texto.
        filter_spec = vim.event.EventFilterSpec()

        collector = event_manager.CreateCollectorForEvents(filter_spec)
        
        # 2. Define o limite exato pedido: 500 eventos
        collector.SetCollectorPageSize(500)
        
        # 3. Extrai a última página bruta (os 500 mais recentes do vCenter)
        events = collector.latestPage
        
        collector.DestroyCollector()

        dump_eventos = []
        
        if events:
            for event in events:
                msg = getattr(event, 'fullFormattedMessage', 'Sem mensagem')
                event_class = type(event).__name__
                event_type_id = getattr(event, 'eventTypeId', 'N/A')
                
                vm_name = "Desconhecida"
                if getattr(event, 'vm', None) and event.vm is not None:
                    vm_name = event.vm.name

                dump_eventos.append({
                    "vm_name": vm_name,
                    "data_evento": event.createdTime.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "mensagem": msg,
                    "tipo_evento": f"Classe: {event_class} | ID: {event_type_id}"
                })

        # Devolve os 500 eventos para o Ansible printar na tela
        print(json.dumps(dump_eventos))

    except Exception as e:
        # Se a biblioteca pyvmomi der crash lendo o banco sem filtros (como o bug do ContentLibrary),
        # ele vai imprimir o erro na tela do Ansible para sabermos a verdade!
        print(json.dumps([{
            "vm_name": "CRASH_PYVMOMI", 
            "data_evento": "N/A", 
            "mensagem": f"A API falhou ao ler o evento bruto: {str(e)}", 
            "tipo_evento": type(e).__name__
        }]))
        sys.exit(0)

if __name__ == '__main__':
    main()