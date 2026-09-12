# Ansible homelab provisioning

This project turns a fresh Ubuntu host into a reusable homelab development
machine. It installs administration and networking tools, C/C++ build tools,
an eBPF toolchain, pinned Go and Go eBPF tooling, Rust and Cargo, Docker
Engine with Compose, kubectl, SSH, and optional TigerVNC remote desktop support.

Base provisioning deliberately does **not** install k3s, CUPS, applications,
or firewall policy. k3s has its own cluster playbook so machines can be
provisioned without automatically joining a cluster.

## Prerequisites

The controller needs Ansible and SSH access to each target. The target must be
Ubuntu and should have Python 3 and OpenSSH Server available. On a fresh host:

```bash
ssh-copy-id razvan@192.168.50.20
ssh razvan@192.168.50.20
sudo visudo -f /etc/sudoers.d/razvan
```

Add this line through `visudo`:

```text
razvan ALL=(ALL:ALL) NOPASSWD: ALL
```

Passwordless sudo lets unattended, `become: true` tasks run without
`--ask-become-pass`. Only grant it to the trusted administration account.

## Inventory and variables

Edit `inventory.ini`, uncomment a host, and replace its example address. The
playbook targets the reusable `provision_targets` group, never a hardcoded host.
For example:

```ini
[mini_pcs]
mini-pc ansible_host=192.168.50.20

[provision_targets:children]
mini_pcs





[all:vars]
ansible_user=razvan
```

Feature switches and pinned versions live in `group_vars/all.yml`. Host- or
group-specific files can override them. The architecture defaults to `amd64`;
set `go_arch: arm64` for an `aarch64` target. Both official checksums are
included.

Test connectivity and inspect changes first:

```bash
ansible all -m ping
ansible-playbook distributions.yml
ansible-playbook provision.yml --check --diff
```

`distributions.yml` only gathers facts and prints each reachable host's
distribution, OS family, package and service managers, architecture, and memory
cgroup availability; it does not install or change anything.

Provision every target, or only one host:

```bash
ansible-playbook provision.yml
ansible-playbook provision.yml --limit mini-pc
```

Upgrade the default `homelab` group, one host, or another inventory group:

```bash
ansible-playbook update.yml
ansible-playbook update.yml --limit mini-pc
ansible-playbook update.yml -e update_target_group=provision_targets
```

## Roles

- `common` installs SSH, CLI, administration, networking, and debugging tools.
  It installs UFW but does not activate or configure firewall policy.
- `development` installs compilers, build systems, autotools, and GDB.
- `ebpf` installs Clang, LLVM, libbpf, bpftool, ELF/zlib development libraries,
  and headers matching `ansible_kernel`. Missing matching headers fail with an
  actionable message.
- `golang` downloads the checksum-verified upstream archive into
  `/usr/local/go`. It installs pinned `bpf2go` as the normal user under
  `~/go/bin`; profile snippets expose both paths.
- `rust` installs rustup, stable Rust, Cargo, rustfmt, and clippy for the normal
  user under `~/.cargo` and `~/.rustup`.
- `docker` uses Docker's official signed Ubuntu apt repository, enables the
  engine, installs Buildx and Compose, and appends the user to the `docker`
  group. Log out and back in before using Docker without sudo.
- `kubectl` installs the Kubernetes client from the official versioned apt
  repository. `kubernetes_minor_version` selects its minor release channel.
- `vnc` installs TigerVNC. It provides a separate X11 desktop, so it does not
  depend on whether the physical Ubuntu session uses X11 or Wayland.

## VNC bootstrap and access

The default VNC session is display `:1`, TCP port `5901`. No VNC password is
stored in this repository. After the first provisioning run, log into the host
as the primary user and initialize it interactively:

```bash
tigervncpasswd ~/.vnc/passwd
```

Rerun `provision.yml`; Ansible will secure the password file and enable
`homelab-vnc.service`. On Ubuntu Server, set this before provisioning so the
role installs XFCE:

```yaml
install_desktop_environment: true
```

With its secure default, TigerVNC listens only on loopback. Connect through an
SSH tunnel (or change `vnc_localhost_only` only when a trusted LAN/VPN and its
firewall policy are in place):

```bash
ssh -L 5901:localhost:5901 razvan@192.168.50.20
```

Then point Remmina at `localhost:5901`. Check the service with:

```bash
systemctl status homelab-vnc
ss -lntp | grep 5901
```

## Verification

Most roles verify their important commands during the run. Useful manual checks
are:

```bash
git --version && curl --version && jq --version && tmux -V
gcc --version && g++ --version && cmake --version && gdb --version
clang --version && llvm-config --version && bpftool version
test -d "/usr/src/linux-headers-$(uname -r)"
go version && bpf2go -h
rustc --version && cargo --version
docker --version && docker compose version
kubectl version --client
```

The roles use package state, checksums, `creates`, templates, and service state,
so it is safe and expected to rerun `provision.yml`. A second run should be
mostly `ok`; rustup may contact its update channel and apt metadata can refresh.

## Adding machines and future roles

Add the host to a category such as `mini_pcs` or `raspberry_pis`, then include
that category beneath `provision_targets:children` when it should receive the
base roles. Use inventory variables to override versions or feature switches.

## k3s cluster bootstrap

k3s remains separate from base provisioning. The initial implementation
supports Debian-family hosts using apt and systemd on x86_64, aarch64, or
armv7l, with exactly one control-plane server and zero or more workers. Select
the roles explicitly in `inventory.ini`:

```ini
[k3s_control_plane]
vm1

[k3s_workers]
# pi1
# pi2

[k3s_cluster:children]
k3s_control_plane
k3s_workers
```

Hosts can appear in several groups; the aliases above refer to hosts declared
elsewhere in the same inventory. Ensure each alias and machine hostname is
unique, its address is stable, and SSH/passwordless sudo work before starting.

Bootstrap or safely reconcile the entire configured cluster with:

```bash
ansible k3s_cluster -m ping
ansible-playbook k3s.yml
```

Do not use `--limit` for the initial cluster bootstrap: all configured cluster
members should participate in the orchestration. The playbook:

1. validates the inventory topology;
2. installs the pinned server on `k3s_control_plane`;
3. waits for the Kubernetes API on TCP `6443`;
4. reads the generated join token with `no_log: true`;
5. installs and joins every `k3s_workers` host; and
6. waits for every inventory node to report `Ready`.

The token is not stored in inventory. k3s keeps it on the server and Ansible
holds it in memory only long enough to render each worker's root-only
`/etc/rancher/k3s/config.yaml`. The playbook is safe to rerun and also upgrades
server and agent binaries when `k3s_version` changes.

The common role verifies that the memory cgroup controller is available before
installing k3s. If it is disabled on Raspberry Pi OS, append
`cgroup_memory=1 cgroup_enable=memory` to `/boot/firmware/cmdline.txt` (or
`/boot/cmdline.txt` on older releases), reboot, and rerun the playbook.

### Disposable Multipass test cluster

Create three local Ubuntu 24.04 VMs (one server and two workers) and generate a
dedicated Ansible inventory with:

```bash
./scripts/multipass-lab.py create
ansible-playbook -i inventory.multipass.ini distributions.yml
ansible -i inventory.multipass.ini k3s_cluster -m ping
ansible-playbook -i inventory.multipass.ini k3s.yml
```

The script reuses the key recorded in an existing generated inventory, then
falls back to `~/.ssh/id_ed25519` or `~/.ssh/id_rsa`. Select another key pair by
setting `MULTIPASS_LAB_SSH_KEY` to the private key path. Existing lab instances
are started and reused. Inspect or permanently remove the three specifically
named instances with:

```bash
./scripts/multipass-lab.py status
./scripts/multipass-lab.py destroy
```

The generated inventory and its isolated SSH known-hosts file are ignored by
Git. The normal `inventory.ini` and physical homelab hosts are never targeted.

Cluster settings are in `group_vars/all.yml`:

```yaml
k3s_version: "v1.36.4+k3s1"
k3s_api_port: 6443
k3s_server_extra_config: {}
k3s_agent_extra_config: {}
```

The server kubeconfig remains at `/etc/rancher/k3s/k3s.yaml`, mode `0640`, and
is readable by `k3s_kubeconfig_group` (the primary user's group by default).
After logging in again, the profile sets `KUBECONFIG` automatically. To use it
immediately in the current shell:

```bash
source /etc/profile.d/k3s.sh
kubectl get nodes -o wide
kubectl get pods --all-namespaces
```

k3s uses its embedded containerd by default. The Docker Engine installed by
`provision.yml` can coexist with it but is not the Kubernetes container runtime.
High-availability multi-server k3s is intentionally not part of this first
version; it requires an odd number of server nodes and additional datastore,
endpoint, quorum, backup, and upgrade decisions.

## Troubleshooting

- `UNREACHABLE` or `Permission denied`: confirm the IP/user, run `ssh` manually,
  copy the public key again, and inspect `ssh -v` output.
- A sudo password prompt or `Missing sudo password`: validate the sudoers
  drop-in with `sudo visudo -c` and test `sudo -n true` on the target.
- Missing kernel headers: enable the appropriate Ubuntu repositories, update
  packages, reboot into the installed Ubuntu kernel, and provision again.
- Docker permission denied: start a new login session after group membership
  changes; confirm with `id` that `docker` is listed.
- VNC exits immediately: inspect `journalctl -u homelab-vnc`; on a server with
  no desktop, enable `install_desktop_environment` and rerun the playbook.
- k3s API timeout: verify the controller and workers can reach the control-plane
  address on TCP `6443`, and check `journalctl -u k3s` on the server.
- A worker does not join: check `journalctl -u k3s-agent` on that worker and
  confirm it can resolve or reach `k3s_server_address`.
