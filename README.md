# Ansible homelab provisioning

This project turns a fresh Ubuntu host into a reusable homelab development
machine. It installs administration and networking tools, C/C++ build tools,
an eBPF toolchain, pinned Go and Go eBPF tooling, Rust and `bpf-linker`, Docker
Engine with Compose, SSH, and optional TigerVNC remote desktop support.

It deliberately does **not** install k3s, CUPS, applications, or firewall
policy. Those belong in separate playbooks so base provisioning stays reusable.

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

[homelab:vars]
ansible_user=razvan
```

Feature switches and pinned versions live in `group_vars/all.yml`. Host- or
group-specific files can override them. The architecture defaults to `amd64`;
set `go_arch: arm64` for an `aarch64` target. Both official checksums are
included.

Test connectivity and inspect changes first:

```bash
ansible all -m ping
ansible-playbook provision.yml --check --diff
```

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
  user under `~/.cargo` and `~/.rustup`. It builds the pinned `bpf-linker` once.
- `docker` uses Docker's official signed Ubuntu apt repository, enables the
  engine, installs Buildx and Compose, and appends the user to the `docker`
  group. Log out and back in before using Docker without sudo.
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
rustc --version && cargo --version && bpf-linker --version
docker --version && docker compose version
```

The roles use package state, checksums, `creates`, templates, and service state,
so it is safe and expected to rerun `provision.yml`. A second run should be
mostly `ok`; rustup may contact its update channel and apt metadata can refresh.

## Adding machines and future roles

Add the host to a category such as `mini_pcs` or `raspberry_pis`, then include
that category beneath `provision_targets:children` when it should receive the
base roles. Use inventory variables to override versions or feature switches.

k3s should later use a separate `k3s.yml` and dedicated `k3s_server` and
`k3s_agent` roles targeting groups such as `k3s_control_plane` and
`k3s_workers`; do not add it to `provision.yml`.

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
