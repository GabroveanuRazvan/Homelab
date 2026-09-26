# Argo-managed homelab resources

The repository uses the App-of-Apps pattern. The root `homelab` Application
watches `argo/applications/` and reconciles the child Argo CD Applications
defined there. Each child Application then watches its own directory under
`argo/workloads/`.

Current Applications:

- `homepage` watches `argo/workloads/homepage/`.
- `traefik-routes` watches `argo/workloads/traefik/`.
- `monitoring` renders the Prometheus Community `kube-prometheus-stack` Helm
  chart with values stored in `argo/values/monitoring/` and applies Grafana
  dashboard ConfigMaps from `argo/workloads/monitoring/`.
- `jellyfin` renders the official Jellyfin Helm chart, mounts the existing NAS
  media exports, and uses values stored in `argo/values/jellyfin/`.

The root Application is bootstrapped or updated explicitly because its
manifest lives outside the directory it watches:

```bash
kubectl apply -f bootstrap/argocd/homelab.yaml
```

After the root exists, changes under `argo/applications/` and the child
workload directories are reconciled from Git by Argo CD.

Grafana dashboards can be built in the UI and exported as V2 resource JSON.
The dashboard JSON is stored under the `jellyfin.json` key of a ConfigMap
labeled `grafana_dashboard: "1"` in `argo/workloads/monitoring/`. Grafana's
dashboard sidecar loads that file. Keep the exported dashboard's
`metadata.name` when updating the ConfigMap so the dashboard URL stays the
same. Commit UI edits back to the ConfigMap; later Git updates overwrite
edits saved only in Grafana.

Required node-placement labels:

```bash
kubectl label node mini-pc homelab.io/storage-safe=true \
  homelab.io/jellyfin=true --overwrite
kubectl label node nas homelab.io/storage-safe=true --overwrite
```

Grafana and Prometheus use `homelab.io/storage-safe`; Jellyfin uses
`homelab.io/jellyfin`. These labels keep persistent and write-heavy workloads
off the Raspberry Pi SD cards without tainting the control-plane node.

Current HTTP routes:

- `http://argocd.home/`
- `http://traefik.home/dashboard/`
- `http://homepage.home/`
- `http://grafana.home/`
- `http://prometheus.home/`
- `http://jellyfin.home/`
- `http://rackpeek.home/`

The Homepage instance uses read-only Kubernetes permissions to discover
annotated Ingress and Traefik IngressRoute resources. Add `homepage.home` to
the local DNS server before opening it in a browser.

Do not commit plaintext credentials, tokens, private keys, or Kubernetes
Secrets containing real credentials to this directory.
