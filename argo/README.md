# Argo-managed homelab resources

The `homelab` Argo CD Application recursively watches this directory on the
`main` branch. Kubernetes manifests committed and pushed here are reconciled
automatically into the cluster.

The initial resource is `argocd/ingressroute.yaml`. It exposes the Argo CD UI
through K3s's Traefik controller at `https://argocd.home` using Traefik's
default certificate. A browser certificate warning is therefore expected until
a trusted certificate issuer is configured.

Do not commit plaintext credentials, tokens, private keys, or Kubernetes
Secrets containing real credentials to this directory.

