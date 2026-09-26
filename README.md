# Homelab

This repository contains most of the tools and configuration used to set up,
bootstrap, and operate my homelab. It combines host provisioning with Ansible,
a k3s Kubernetes cluster, Argo CD-managed applications, Helm values, standalone
Docker Compose workloads, and supporting automation scripts.

## Homelab topology

```mermaid
%%{init: {'layout': 'elk', 'flowchart': {'curve': 'step', 'nodeSpacing': 60, 'rankSpacing': 80, 'padding': 20, 'subGraphTitleMargin': {'top': 12, 'bottom': 12}}, 'elk': {'algorithm': 'layered', 'aspectRatio': 0.5, 'layered.wrapping.strategy': 'MULTI_EDGE', 'layered.nodePlacement.strategy': 'BRANDES_KOEPF'}, 'themeVariables': {'edgeLabelBackground': 'transparent', 'clusterBkg': 'transparent', 'clusterBorder': '#3f3f46'}}}%%
flowchart TD
    classDef rpknode fill:#1f2937,stroke:#52525b,color:#e5e7eb,stroke-width:1px,stroke-dasharray:3 3
    classDef rpkgroup fill:none,stroke:#3f3f46,color:#a1a1aa,stroke-width:1px,stroke-dasharray:3 3

    n_mini_pc("Mini-PC<br/>desktop"):::rpknode
    n_nas("Nas<br/>desktop"):::rpknode
    n_pi1("Pi1<br/>desktop"):::rpknode
    n_pi2("Pi2<br/>desktop"):::rpknode
    n_router(["Router<br/>router"]):::rpknode
    n_switch[["Switch<br/>switch"]]:::rpknode
    n_ups{"UPS<br/>ups"}:::rpknode

    n_switch ---|"router <-> switch"| n_router
    n_switch ---|"mini-pc <-> switch"| n_mini_pc
    n_switch ---|"pi2 <-> switch"| n_pi2
    n_switch ---|"pi1 <-> switch"| n_pi1
    n_nas ---|"nas <-> router"| n_router

    linkStyle default stroke:#52525b,stroke-width:1.25px,stroke-dasharray:4 4,fill:none
```

## Repository layout

```text
.
├── ansible
│   ├── group_vars
│   │   └── all
│   └── roles
│       ├── common
│       │   ├── defaults
│       │   └── tasks
│       ├── development
│       │   ├── defaults
│       │   └── tasks
│       ├── docker
│       │   ├── defaults
│       │   └── tasks
│       ├── ebpf
│       │   ├── defaults
│       │   └── tasks
│       ├── golang
│       │   ├── defaults
│       │   └── tasks
│       ├── helm
│       │   ├── defaults
│       │   └── tasks
│       ├── k3s_agent
│       │   ├── defaults
│       │   ├── handlers
│       │   ├── tasks
│       │   └── templates
│       ├── k3s_common
│       │   ├── defaults
│       │   └── tasks
│       ├── k3s_server
│       │   ├── defaults
│       │   ├── handlers
│       │   ├── tasks
│       │   └── templates
│       ├── kubectl
│       │   ├── defaults
│       │   └── tasks
│       └── rust
│           ├── defaults
│           └── tasks
├── argo
│   ├── applications
│   ├── values
│   │   ├── jellyfin
│   │   └── monitoring
│   └── workloads
│       ├── homepage
│       ├── jellyfin
│       ├── monitoring
│       ├── rackpeek
│       └── traefik
├── bootstrap
│   └── argocd
├── docker
├── helm
│   └── argocd
└── scripts
    └── argocd

60 directories
```

## Main directories

### `ansible/`

Ansible inventory, shared variables, playbooks, and reusable roles for
provisioning Debian/Ubuntu hosts. The roles install the common administration
toolset and development environment, Docker, Go, Rust, eBPF tooling, kubectl,
and Helm. The k3s roles bootstrap and manage the Kubernetes server and agent
nodes separately from general host provisioning.

### `argo/`

The desired Kubernetes application state reconciled by Argo CD. It contains
Argo CD `Application` resources, chart values, raw workload manifests, storage
configuration, monitoring resources, and Traefik routes for homelab services.

### `bootstrap/`

The small amount of configuration that must be applied before GitOps can take
over. The root Argo CD application in this directory connects the cluster to
the application definitions under `argo/`.

### `docker/`

Docker Compose definitions for services that can run directly on a Docker
host, independently of the k3s cluster. These currently cover Jellyfin,
Pi-hole, and qBittorrent.

### `helm/`

Helm configuration used to install or configure foundational cluster services.
At present it contains the values used for the initial Argo CD installation.

### `scripts/`

Operational helper scripts. The Argo CD scripts install and remove Argo CD and
configure its Git repository credentials. `multipass-lab.py` creates a
disposable local multi-node environment for testing the Ansible and k3s setup.

