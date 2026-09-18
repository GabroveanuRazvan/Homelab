# Argo-managed homelab resources

The `homelab` Argo CD Application recursively watches this directory on the
`main` branch. Kubernetes manifests committed and pushed here are reconciled
automatically into the cluster.

Traefik routes are kept together in `traefik/`. Application resources are
grouped by application, such as the Homepage deployment under `homepage/`.

Current HTTP routes:

- `http://argocd.home/`
- `http://traefik.home/dashboard/`
- `http://homepage.home/`

The Homepage instance uses read-only Kubernetes permissions to discover
annotated Ingress and Traefik IngressRoute resources. Add `homepage.home` to
the local DNS server before opening it in a browser.

Do not commit plaintext credentials, tokens, private keys, or Kubernetes
Secrets containing real credentials to this directory.
