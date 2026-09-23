# RackPeek

Argo CD deploys RackPeek from this directory. Its writable YAML inventory
(`config.yaml`) lives on the `rackpeek-config` PVC mounted at `/app/config`.
The deployment uses one replica and the `Recreate` strategy to avoid two pods
writing to the same file during an update.

The PVC uses k3s `local-path` storage. Its data stays on the node where the
volume is first created, even if another storage-safe node is available. Back
up the inventory file; neither Git nor Argo CD backs up data written to a PVC.

Add `rackpeek.home` to Pi-hole's local DNS records, pointing it at a k3s node
that serves Traefik, then open `http://rackpeek.home/`. The route is intended
for the trusted LAN, not public Internet exposure.
