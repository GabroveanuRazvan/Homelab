# Argo-managed homelab resources

The repository uses the App-of-Apps pattern. The root `homelab` Application
watches `argo/applications/` and reconciles the child Argo CD Applications
defined there. Each child Application then watches its own directory under
`argo/workloads/`.

Current Applications:

- `homepage` watches `argo/workloads/homepage/`.
- `traefik-routes` watches `argo/workloads/traefik/`.
- `monitoring` renders the Prometheus Community `kube-prometheus-stack` Helm
  chart with values stored in `argo/values/monitoring/`.

The root Application is bootstrapped or updated explicitly because its
manifest lives outside the directory it watches:

```bash
kubectl apply -f bootstrap/argocd/homelab.yaml
```

After the root exists, changes under `argo/applications/` and the child
workload directories are reconciled from Git by Argo CD.

Current HTTP routes:

- `http://argocd.home/`
- `http://traefik.home/dashboard/`
- `http://homepage.home/`
- `http://grafana.home/`

The Homepage instance uses read-only Kubernetes permissions to discover
annotated Ingress and Traefik IngressRoute resources. Add `homepage.home` to
the local DNS server before opening it in a browser.

Do not commit plaintext credentials, tokens, private keys, or Kubernetes
Secrets containing real credentials to this directory.
