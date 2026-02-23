
# 🇨🇭 Canivete Suíço de Operações VMware (CaniveteOps)

Este repositório contém uma suíte de automações em Ansible/AWX focada na resolução proativa, auditoria e troubleshooting avançado de ambientes VMware vSphere (vCenter/ESXi). O objetivo é fornecer ferramentas cirúrgicas e confiáveis para a equipe de infraestrutura, eliminando tarefas manuais repetitivas e prevenindo incidentes silenciosos.

## 📋 Sobre o Projeto

O **CaniveteOps** é construído de forma modular (roles) para ser executado via AWX (Ansible Tower). Atualmente, a suíte conta com duas ferramentas principais focadas em resiliência e saúde da rede:

### 1. Relatório Definitivo de HA (`relatorio-ha-vcenter`)
Audita o vCenter em busca de Máquinas Virtuais que sofreram queda e foram reiniciadas pelo vSphere HA (High Availability) nas últimas 48 horas. 
* **O Problema Resolvido:** Consultas nativas no vCenter frequentemente omitem eventos concorrentes ou falham devido a bugs da API ao ler logs corrompidos.
* **A Solução:** Utiliza um script customizado em Python (`pyvmomi`) que interroga cada VM individualmente, garantindo precisão absoluta e blindagem contra perdas de logs.

### 2. Auditor de IPs Duplicados (`check-duplicate-ip`)
Varre 100% dos hosts ESXi da infraestrutura em busca de conflitos de rede nos adaptadores VMkernel (Management, vMotion, vSAN, etc).
* **O Problema Resolvido:** IPs duplicados em interfaces VMkernel causam falhas intermitentes de vMotion e quedas de gerência difíceis de diagnosticar.
* **A Solução:** Rotina 100% nativa em Ansible que extrai a topologia (Datacenters > Clusters > Hosts > Network Facts) e cruza todos os endereços IPv4 em memória via Jinja2, ignorando inteligentemente IPs de Link-Local (169.254.x.x) e Loopback.

---

## ⚙️ Pré-requisitos

Para executar as roles deste repositório, o ambiente de execução (AWX Execution Environment) deve possuir:

1. **Credenciais vCenter:** Variáveis de ambiente configuradas no AWX (`VMWARE_HOST`, `VMWARE_USER`, `VMWARE_PASSWORD`).
2. **Dependências Python:** Pacote `pyvmomi` instalado no contêiner para o módulo de relatórios de HA.
3. **Coleções Ansible:** `community.vmware` instalada (compatível com módulos clássicos como `vmware_cluster_info` e `vmware_host_facts`).
4. **Notificações:** Variável `slack_webhook_url` (ou via env `SLACK_WEBHOOK_URL`) configurada para o disparo de alertas.

---

## 🚀 Como Executar (Via AWX)

As ferramentas foram projetadas para rodar de forma agendada (Cron) ou sob demanda através do AWX.

1. Acesse o **AWX** e vá em **Templates**.
2. Selecione o Job Template correspondente à ferramenta do CaniveteOps que deseja executar.
3. (Opcional) Responda ao *Survey* caso o Job exija algum parâmetro de entrada específico (ex: limite de dias para busca de HA).
4. Clique em **Launch**.
5. Acompanhe os alertas diretamente no canal do Slack configurado.

---

## 🧠 O que o Ansible faz por trás dos panos?

### Na Role `relatorio-ha-vcenter`:
* Ignora consultas globais do vCenter que causam "Crash Silencioso".
* Varre a infraestrutura buscando as VMs ligadas.
* Injeta requisições assíncronas isoladas por VM (`QueryEvents` filtrando por `VmRestartedByHAEvent`), forçando a API a revelar eventos que ocorreram no mesmo exato milissegundo.

### Na Role `check-duplicate-ip`:
* Mapeia a infraestrutura em cascata, não dependendo de arquivos TXT locais.
* Executa a coleta de *facts* de forma tolerante a falhas (`ignore_errors: yes`), para que um ESXi em manutenção não quebre a auditoria do restante do datacenter.
* Agrupa os milhares de IPs extraídos em memória utilizando lógica Jinja2.
* Aciona um **Hard Stop** (`failed_when`) no AWX caso detecte o conflito, colorindo o Job de vermelho para fins de auditoria histórica.

---

## 🔔 Notificações e Alertas (Slack)

As roles são programadas para enviar relatórios ricos formatados em *mrkdwn* diretamente para o Slack via Webhook nativo (`ansible.builtin.uri`), garantindo compatibilidade universal.

**Exemplo de detecção de conflito de IP:**
> 🚨 **ALERTA CRÍTICO: Conflito de IP (VMkernel) Detectado!** 🚨
> 
> **IP Duplicado:** `10.107.61.44`
> **Sendo utilizado simultaneamente em:**
> • tpsp1esx3n00014.dominio.local (vmk2)
> • tpsp1esx3n00044.dominio.local (vmk2)

***

**Dica:** Conforme formos adicionando novas roles ao nosso Canivete (ex: limpeza de snapshots órfãos, verificação de datastores lotados, etc.), basta ir adicionando pequenos blocos na seção "Ferramentas" deste README. Ficou muito profissional! O que achou?