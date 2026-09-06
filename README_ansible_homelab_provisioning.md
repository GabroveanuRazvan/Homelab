# Homelab Ubuntu Provisioning with Ansible

## Goal

Build an Ansible-based provisioning setup that can take a fresh Ubuntu installation on a new mini-PC and configure it into a standard homelab/development machine.

The provisioning should be reusable for future machines, not hardcoded only for this mini-PC.

The target system is expected to be Ubuntu on x86_64.

The provisioning should install and configure:

- common CLI/admin utilities
- networking/debugging utilities
- development tools
- eBPF development tools
- Go
- Rust
- Docker Engine + Compose
- VNC server / remote desktop support
- SSH access
- sensible user/group setup

Do **not** install or configure CUPS.

Do **not** install k3s as part of the base provisioning. Kubernetes/k3s should remain a separate role/playbook so that not every provisioned machine automatically becomes part of the cluster.

---

# Existing Ansible assumptions

The Ansible controller already exists and can connect to the target machines over SSH.

Example inventory:

```ini
[homelab]
pi1 ansible_host=192.168.50.10
pi2 ansible_host=192.168.50.11
nas ansible_host=192.168.50.12
mini-pc ansible_host=192.168.50.20

[homelab:vars]
ansible_user=razvan
```

The machines are expected to allow passwordless sudo for the Ansible user, e.g.:

```text
razvan ALL=(ALL:ALL) NOPASSWD: ALL
```

Therefore playbooks should generally use:

```yaml
become: true
```

and should not require `--ask-become-pass`.

---

# Desired repository structure

Create a clean Ansible project with something close to:

```text
ansible/
├── ansible.cfg
├── inventory.ini
├── provision.yml
├── group_vars/
│   └── all.yml
├── roles/
│   ├── common/
│   │   └── tasks/
│   │       └── main.yml
│   ├── development/
│   │   └── tasks/
│   │       └── main.yml
│   ├── ebpf/
│   │   └── tasks/
│   │       └── main.yml
│   ├── golang/
│   │   └── tasks/
│   │       └── main.yml
│   ├── rust/
│   │   └── tasks/
│   │       └── main.yml
│   ├── docker/
│   │   └── tasks/
│   │       └── main.yml
│   └── vnc/
│       └── tasks/
│           └── main.yml
└── README.md
```

If additional files are needed, such as handlers, defaults, templates, or vars, create them using normal Ansible role conventions.

Prefer proper roles over putting everything in one large playbook.

---

# Top-level playbook

Create `provision.yml`.

It should apply the required roles to a configurable target group.

Example:

```yaml
---
- name: Provision homelab development machines
  hosts: provision_targets
  become: true

  roles:
    - common
    - development
    - ebpf
    - golang
    - rust
    - docker
    - vnc
```

Do not hardcode `mini-pc` directly in the playbook.

The inventory should be able to contain something like:

```ini
[provision_targets]
mini-pc ansible_host=192.168.50.20
```

This lets the same provisioning process be reused later.

---

# General implementation requirements

All roles must be:

- idempotent
- safe to rerun
- understandable
- split logically
- implemented using Ansible modules where practical

Prefer:

```yaml
ansible.builtin.apt
ansible.builtin.package
ansible.builtin.file
ansible.builtin.copy
ansible.builtin.template
ansible.builtin.user
ansible.builtin.service
ansible.builtin.get_url
ansible.builtin.apt_repository
ansible.builtin.command
```

Avoid arbitrary `shell` commands unless there is a good reason.

When `command` or `shell` is unavoidable, make the task idempotent using things such as:

```yaml
creates:
changed_when:
failed_when:
```

Do not use shell pipelines where an Ansible module provides the same behavior.

---

# Role: common

Install basic tools expected on essentially every homelab Linux host.

At minimum install:

```text
ca-certificates
curl
git
tmux
ufw
openssh-server
iproute2
net-tools
netcat-openbsd
e2fsprogs
util-linux
jq
tree
htop
rsync
unzip
zip
dnsutils
traceroute
tcpdump
iperf3
lsof
strace
```

Also install:

```text
wget
file
less
bash-completion
```

unless there is a reason not to.

Ensure the SSH service is enabled and running.

Do not aggressively modify SSH security settings yet. This provisioning should not risk locking the user out.

Do not enable restrictive UFW rules automatically unless the configuration is explicitly defined.

Installing `ufw` is enough for the first version.

Run apt cache updates using Ansible's apt module rather than:

```bash
apt update
```

directly.

Example desired semantics:

```yaml
update_cache: true
cache_valid_time: 3600
```

---

# Role: development

Install general compiler/build/debug tooling.

Install at least:

```text
build-essential
make
cmake
pkg-config
gdb
```

Also include common development dependencies:

```text
autoconf
automake
libtool
```

It is fine to include these even if not every project immediately needs them.

Do not install large IDEs or GUI development environments.

---

# Role: eBPF

This machine will be used for eBPF development.

Install at least:

```text
clang
llvm
libbpf-dev
bpftool
```

Also install kernel headers matching the currently running kernel.

Equivalent shell intent:

```bash
sudo apt install linux-headers-$(uname -r)
```

But implement this correctly in Ansible.

The relevant Ansible fact should normally be:

```text
ansible_kernel
```

For example:

```text
linux-headers-{{ ansible_kernel }}
```

If Ubuntu package availability means that exact headers cannot be installed, fail with a useful error rather than silently ignoring it.

Also install useful ELF/BPF development packages where appropriate:

```text
libelf-dev
zlib1g-dev
```

Consider installing:

```text
linux-tools-common
```

and the matching kernel tools package if useful and available.

Do not assume ARM-specific include paths.

The new mini-PC is expected to be x86_64.

The previous Raspberry Pi eBPF setup needed ARM64-specific handling such as:

```text
/usr/include/aarch64-linux-gnu
```

Do not hardcode that into the generic x86_64 provisioning role.

The role should verify that these commands exist after installation:

```bash
clang --version
llvm-config --version
bpftool version
```

It is acceptable to perform checks using `command` with:

```yaml
changed_when: false
```

---

# Role: Go

Install Go in a predictable way.

Do not blindly rely on Ubuntu's `golang-go` package if it is significantly behind the current stable Go release.

Prefer a version-controlled installation where the Go version is specified in variables.

For example in `group_vars/all.yml`:

```yaml
go_version: "CHANGE_ME"
go_arch: "amd64"
```

Codex should choose a sensible current stable Go version at implementation time, but keep the version controlled from a variable.

Install Go under:

```text
/usr/local/go
```

and make it available system-wide through PATH.

A file such as:

```text
/etc/profile.d/go.sh
```

is acceptable.

Expected PATH addition:

```bash
export PATH="$PATH:/usr/local/go/bin"
```

Do not repeatedly download/install Go on every Ansible run when the requested version is already installed.

Check:

```bash
go version
```

after installation.

---

# Go eBPF tooling

Install the Cilium eBPF Go tooling required for development.

The relevant package is:

```text
github.com/cilium/ebpf
```

The important utility is:

```text
bpf2go
```

Equivalent manual installation:

```bash
go install github.com/cilium/ebpf/cmd/bpf2go@latest
```

However, avoid uncontrolled `@latest` if possible.

Prefer defining the desired version in variables, for example:

```yaml
bpf2go_version: "latest"
```

or pinning an actual version if easy to maintain.

Install user Go binaries into a predictable location.

For example:

```text
/home/{{ ansible_user }}/go/bin
```

Ensure that location is added to the user's PATH.

Be careful that tasks running with:

```yaml
become: true
```

do not accidentally install Go user tools into `/root/go`.

Use `become_user` when appropriate.

---

# Role: Rust

Install Rust using `rustup`, preferably for the normal Ansible login user rather than root.

Expected manual behavior is similar to:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

But implement it idempotently and safely.

Avoid executing an installer every run.

Rust should be installed under the user's home directory:

```text
~/.cargo
~/.rustup
```

Ensure:

```text
~/.cargo/bin
```

is available in PATH for interactive shells.

Install or configure:

```text
rustc
cargo
rustfmt
clippy
```

through rustup.

Verify:

```bash
rustc --version
cargo --version
```

---

# Rust eBPF tooling

Install:

```text
bpf-linker
```

The user has used this previously for Rust eBPF programs.

Equivalent manual behavior:

```bash
cargo install bpf-linker
```

Make the task idempotent.

Do not reinstall it on every playbook execution if the binary already exists.

Verify:

```bash
bpf-linker --version
```

Run Cargo installation as the normal user, not root.

---

# Role: Docker

Install Docker Engine using Docker's official apt repository.

Do not simply install Ubuntu's old `docker.io` package unless there is a strong reason.

Install:

```text
docker-ce
docker-ce-cli
containerd.io
docker-buildx-plugin
docker-compose-plugin
```

Implementation should:

1. install prerequisite packages
2. install Docker's repository signing key
3. add the official Docker apt repository
4. update apt cache
5. install Docker packages
6. enable and start Docker
7. add the normal user to the `docker` group

Expected result:

```bash
docker --version
docker compose version
```

should work.

Adding the user to the Docker group should be done with:

```yaml
ansible.builtin.user:
  groups: docker
  append: true
```

Do not remove the user from existing groups.

Document that a new login session may be needed before Docker commands work without sudo.

Do not enable Docker Swarm.

Do not deploy containers in this base role.

---

# Role: VNC / remote desktop

The user wants VNC remote access installed on the mini-PC.

The user has previously used VNC/Remmina and WayVNC on Raspberry Pi systems.

The implementation should support Ubuntu appropriately.

First determine whether the target Ubuntu installation is expected to have a GUI.

Assume for this project that the mini-PC should support a graphical desktop and remote access.

The role should install a lightweight, maintainable VNC setup.

Prefer one of:

- TigerVNC
- WayVNC if the selected Ubuntu desktop/session makes it the more appropriate solution

Avoid mixing multiple VNC servers unnecessarily.

The implementation should be explicit about whether the server supports:

- X11
- Wayland
- both

The user's client machine can use Remmina, so the server only needs to expose a standard VNC-compatible endpoint.

The role should:

- install the chosen VNC server
- configure it for the normal user
- configure a systemd service where appropriate
- make the service restartable/manageable through systemd
- avoid storing a plaintext VNC password in the repository
- document any initial password/bootstrap step that cannot safely be automated
- document the default port, typically `5900` or `5901` depending on the implementation

If a VNC password can be generated securely from an Ansible Vault variable, structure the role to support that.

For example, support a variable like:

```yaml
vnc_password: "{{ vault_vnc_password }}"
```

but do not commit a real password.

The role should not expose the VNC service to the public Internet.

Do not create router port-forwarding rules.

Assume access occurs from the LAN or through WireGuard/VPN.

If UFW rules are added for VNC, scope them conservatively to the local network if possible.

If the correct VNC implementation depends strongly on whether Ubuntu is installed as Server vs Desktop or whether GNOME is running under Wayland, document that clearly in the project README and make the role easy to adjust.

---

# Desktop environment

Do not silently install a huge desktop stack unless required.

If the new Ubuntu installation is Ubuntu Desktop, reuse the existing desktop.

If the target is Ubuntu Server with no desktop installed, VNC will require a desktop environment.

In that case, prefer a relatively lightweight desktop rather than installing unnecessary software.

A reasonable option is XFCE.

If implementing support for this scenario, make desktop installation conditional through a variable such as:

```yaml
install_desktop_environment: false
```

When `true`, install the chosen lightweight desktop environment.

Do not assume this should always happen.

---

# Variables

Create useful configurable variables in:

```text
group_vars/all.yml
```

or role defaults.

Potential variables:

```yaml
primary_user: "{{ ansible_user }}"

go_version: "..."
go_arch: "amd64"

install_desktop_environment: false

install_vnc: true

install_docker: true

install_ebpf_tools: true

install_go: true

install_rust: true
```

Use role defaults where that makes more sense.

Avoid excessive abstraction, but do not hardcode machine-specific details.

---

# Package architecture handling

The first target mini-PC is expected to be:

```text
x86_64 / amd64
```

Still, avoid unnecessary architecture assumptions when simple Ansible facts can be used.

Use:

```text
ansible_architecture
```

where useful.

For Docker apt repository architecture, correctly translate Ansible architecture values to Debian architecture names if necessary.

Example conceptual mapping:

```text
x86_64  -> amd64
aarch64 -> arm64
```

This is useful because the same Docker role may later be reused for Raspberry Pis.

---

# Inventory groups

Keep the inventory organized so roles can later target different kinds of machines.

Suggested direction:

```ini
[raspberry_pis]
pi1 ansible_host=...
pi2 ansible_host=...

[nas]
nas ansible_host=...

[mini_pcs]
mini-pc ansible_host=...

[provision_targets]
mini-pc

[k3s_control_plane]
pi1

[k3s_workers]
pi2
nas
```

Do not implement k3s provisioning yet, but structure things so a later `k3s` role can naturally use these groups.

---

# k3s explicitly excluded from base provisioning

Do not install k3s in `provision.yml`.

Later there should probably be a separate playbook like:

```text
k3s.yml
```

with roles such as:

```text
roles/
├── k3s_server/
└── k3s_agent/
```

This is intentionally out of scope for the first implementation.

---

# Updates/upgrades

The project should also contain a reusable package-upgrade playbook.

Create something such as:

```text
update.yml
```

Equivalent intent:

```bash
sudo apt update
sudo apt upgrade -y
```

Use Ansible's apt module:

```yaml
- name: Update apt cache
  ansible.builtin.apt:
    update_cache: true

- name: Upgrade installed packages
  ansible.builtin.apt:
    upgrade: yes
```

This should work against any selected inventory group.

---

# ansible.cfg

Create a local `ansible.cfg`.

At minimum:

```ini
[defaults]
inventory = inventory.ini
```

Useful additional safe settings are acceptable.

Do not disable SSH host-key checking just for convenience unless clearly documented.

---

# Testing and verification

After provisioning, run validation tasks or document these commands.

## Core

```bash
git --version
curl --version
jq --version
tree --version
htop --version
tmux -V
iperf3 --version
tcpdump --version
strace --version
```

## Compiler/debug

```bash
gcc --version
g++ --version
make --version
cmake --version
gdb --version
```

## eBPF

```bash
clang --version
bpftool version
```

Verify kernel headers exist for:

```bash
uname -r
```

## Go

```bash
go version
which go
bpf2go
```

or:

```bash
bpf2go -h
```

## Rust

```bash
rustc --version
cargo --version
bpf-linker --version
```

## Docker

```bash
docker --version
docker compose version
systemctl status docker
```

A new login session may be required before testing Docker without sudo after group membership changes.

## VNC

Verify the chosen VNC systemd unit.

Examples depending on implementation:

```bash
systemctl status wayvnc
```

or:

```bash
systemctl status vncserver@...
```

Confirm it is listening:

```bash
ss -lntp | grep 590
```

---

# Idempotency test

A successful implementation must survive being executed twice.

Run:

```bash
ansible-playbook provision.yml
ansible-playbook provision.yml
```

The second execution should report mostly:

```text
ok
```

rather than reinstalling/reconfiguring everything.

Some tasks such as apt metadata refresh may legitimately report changes depending on implementation, but language runtimes and downloaded tools should not be reinstalled unnecessarily.

---

# Check mode

Where possible, support:

```bash
ansible-playbook provision.yml --check
```

Some external installers may not support meaningful check mode, but avoid breaking check mode unnecessarily.

---

# Security requirements

Do not:

- commit passwords
- commit private SSH keys
- expose VNC to the Internet
- disable the firewall globally
- weaken SSH configuration unnecessarily
- run language user installers as root when they belong to the normal user
- use `curl | sudo sh` when repository/key-based installation is available
- add untrusted apt repositories

Secrets should be designed to work with Ansible Vault.

Potential future files:

```text
group_vars/all/vault.yml
```

or equivalent.

---

# README requirements

The repository README generated by Codex should explain:

1. what the project provisions
2. prerequisites
3. how SSH authentication is expected to work
4. why passwordless sudo is used
5. inventory setup
6. how to run the provisioning playbook
7. how to provision only one host
8. how to run the update playbook
9. role descriptions
10. how Go is installed
11. how Rust is installed
12. how Docker is installed
13. how eBPF dependencies are installed
14. how VNC is configured
15. any manual VNC password/bootstrap step
16. how to verify installation
17. how to rerun safely
18. how to add another machine
19. how to add future roles such as k3s
20. troubleshooting common SSH/sudo issues

Example single-host execution:

```bash
ansible-playbook provision.yml --limit mini-pc
```

Example connectivity test:

```bash
ansible all -m ping
```

---

# Expected coding quality

The resulting Ansible should feel like infrastructure code, not a collection of shell commands.

Prefer this:

```yaml
- name: Install common packages
  ansible.builtin.apt:
    name: "{{ common_packages }}"
    state: present
    update_cache: true
```

over dozens of individual apt tasks.

Use handlers for services when configuration changes require restarts.

Example:

```yaml
notify: Restart something
```

Use `defaults/main.yml` for role configuration when appropriate.

Use templates only where configuration genuinely needs interpolation.

Use descriptive task names.

---

# Suggested extra files

Codex may create:

```text
roles/common/defaults/main.yml
roles/development/defaults/main.yml
roles/ebpf/defaults/main.yml
roles/golang/defaults/main.yml
roles/rust/defaults/main.yml
roles/docker/defaults/main.yml
roles/vnc/defaults/main.yml
```

and handlers where needed.

A `.gitignore` should exclude secrets and transient files.

Example items:

```gitignore
*.retry
.vault_pass
vault-password*
```

Do not ignore normal Ansible source files.

---

# First-run workflow

Expected practical workflow for the new mini-PC:

1. Install Ubuntu.
2. Create the normal user.
3. Configure networking.
4. Ensure OpenSSH Server is installed/running.
5. Copy the controller SSH public key:

   ```bash
   ssh-copy-id razvan@MINI_PC_IP
   ```

6. Configure passwordless sudo using a sudoers drop-in:

   ```bash
   sudo visudo -f /etc/sudoers.d/razvan
   ```

   with:

   ```text
   razvan ALL=(ALL:ALL) NOPASSWD: ALL
   ```

7. Add the host to `inventory.ini`.
8. Test:

   ```bash
   ansible mini-pc -m ping
   ```

9. Provision:

   ```bash
   ansible-playbook provision.yml --limit mini-pc
   ```

10. Log out and back in if necessary for Docker group membership.
11. Verify installed tools.
12. Configure/test the VNC client from the laptop using Remmina.

---

# Out of scope for now

Do not add these yet:

- k3s installation
- Kubernetes cluster joining
- CUPS
- Pi-hole
- Grafana
- Prometheus
- Cassandra
- Redis server
- Argo CD
- application deployments
- firewall policy orchestration
- WireGuard server/client provisioning
- personal dotfiles
- IDE installation

Those can become separate roles/playbooks later.

---

# Final desired outcome

After running:

```bash
ansible-playbook provision.yml --limit mini-pc
```

against a fresh Ubuntu installation, the mini-PC should be ready for:

- SSH administration
- Git-based development
- Go development
- Rust development
- C/C++ development
- eBPF development using clang/libbpf/bpftool
- Go eBPF development using `cilium/ebpf` and `bpf2go`
- Rust eBPF development using `bpf-linker`
- Docker and Docker Compose workloads
- networking troubleshooting
- general Linux troubleshooting
- remote graphical access through VNC

The solution should be reusable, modular, idempotent, and easy to extend with future Ansible roles.
