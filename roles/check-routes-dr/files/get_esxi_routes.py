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

        # Extrai todos os hosts ESXi gerenciados pelo vCenter
        container = si.content.viewManager.CreateContainerView(
            si.content.rootFolder, [vim.HostSystem], True
        )
        hosts = container.view

        host_routes = {}

        for esxi in hosts:
            # Ignora hosts que estejam desligados ou desconectados
            if esxi.runtime.connectionState != vim.HostSystem.ConnectionState.connected:
                continue
                
            try:
                routes = []
                # Acessa a tabela de roteamento do kernel do ESXi nativamente via API
                ip_routes = esxi.configManager.networkSystem.networkInfo.routeTableInfo.ipRoute
                
                for r in ip_routes:
                    routes.append({
                        "rede_destino": r.network,
                        "mascara": r.prefixLength,
                        "gateway": r.gateway,
                        "interface": getattr(r, 'deviceName', 'N/A')
                    })
                    
                host_routes[esxi.name] = routes
            except Exception:
                continue

        container.Destroy()
        
        # Retorna o dicionário completo em formato JSON
        print(json.dumps(host_routes))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == '__main__':
    main()