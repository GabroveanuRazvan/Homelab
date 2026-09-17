# Argo CD bootstrap

Ansible provisions the machines and K3s, but it does not manage Kubernetes
resources. Argo CD itself is bootstrapped with Helm; after that, the `homelab`
Application watches the repository's `argo/` directory and reconciles the
manifests committed there.

## 1. Install Argo CD with Helm

The install script pins the `argo-cd` chart to version `10.9.1` and uses
`helm/argocd/values.yaml`:

```bash
./scripts/argocd/install.sh
```

The command is safe to rerun because it uses `helm upgrade --install`.

## 2. Give Argo CD read-only access to the private repository

Generate a dedicated, passwordless deploy key:

```bash
./scripts/argocd/generate-repository-key.sh
```

In GitHub, open this repository's **Settings > Deploy keys > Add deploy key**,
paste the printed public key, and leave **Allow write access** disabled. Argo CD
does not need permission to push changes.

After adding the public key in GitHub, create the labeled Argo CD repository
Secret from the local private key:

```bash
./scripts/argocd/configure-repository.sh
```

The private key is read from `~/.ssh/argocd-homelab` and is never stored in
Git. Override the path with `ARGOCD_REPOSITORY_KEY_PATH` if necessary.

## 3. Publish the desired state

Argo CD reads the remote `main` branch, not the local working tree. Review,
commit, and push the new `argo/`, `bootstrap/`, `helm/`, and `scripts/argocd/`
files before creating the root Application.

## 4. Create the root Application manually

This is the one-time bridge between the Helm installation and GitOps:

```bash
kubectl apply -f bootstrap/argocd/homelab.yaml
kubectl get applications --namespace argocd
```

The Application has automated synchronization, pruning, and self-healing. A
manifest removed from `argo/` will therefore be removed from the cluster after
the corresponding commit reaches `main`.

Watch the first synchronization:

```bash
kubectl get applications --namespace argocd --watch
kubectl get ingressroute --namespace argocd
```

## 5. Resolve and open the ingress

Create a local DNS record mapping `argocd.home` to a K3s node, for example the
control-plane address:

```text
192.168.50.215 argocd.home
```

For a one-off test that does not require changing DNS or `/etc/hosts`:

```bash
curl --insecure \
  --resolve argocd.home:443:192.168.50.215 \
  https://argocd.home/
```

Then open `https://argocd.home` in a browser. Traefik uses its default
certificate, so a certificate warning is expected in this first iteration.

The username is `admin`. Retrieve the initial password with:

```bash
kubectl --namespace argocd get secret argocd-initial-admin-secret \
  --output=jsonpath='{.data.password}' | base64 --decode
echo
```

Change the password after the first login. Later, add a trusted certificate
with cert-manager instead of relying on Traefik's default certificate.

## Remove the Helm installation

```bash
./scripts/argocd/uninstall.sh
```

The uninstall script intentionally leaves the namespace and any remaining
resources for inspection rather than deleting them recursively.
