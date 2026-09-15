#!/usr/bin/env python3
"""Create and manage a disposable three-node Multipass k3s lab."""

from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import Iterator, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
ANSIBLE_DIR = PROJECT_DIR / "ansible"
INVENTORY_FILE = ANSIBLE_DIR / "inventory.multipass.ini"
KNOWN_HOSTS_FILE = ANSIBLE_DIR / ".multipass_known_hosts"
MULTIPASS_IMAGE = os.environ.get("MULTIPASS_LAB_IMAGE", "24.04")


@dataclass(frozen=True)
class Instance:
    """Resources assigned to one Multipass instance."""

    name: str
    cpus: int
    memory: str
    disk: str


SERVER = Instance("k3s-server", cpus=2, memory="3G", disk="15G")
WORKER_ONE = Instance("k3s-worker-1", cpus=1, memory="2G", disk="10G")
WORKER_TWO = Instance("k3s-worker-2", cpus=1, memory="2G", disk="10G")
INSTANCES = (SERVER, WORKER_ONE, WORKER_TWO)


class LabError(RuntimeError):
    """A user-facing lab management error."""


def run(
    command: Sequence[str],
    *,
    check: bool = True,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a command and optionally return its captured output."""

    return subprocess.run(
        command,
        check=check,
        text=True,
        capture_output=capture_output,
    )


def require_multipass() -> None:
    """Fail early when the Multipass client is unavailable."""

    if shutil.which("multipass") is None:
        raise LabError("Required command not found: multipass")


def find_ssh_private_key() -> Path:
    """Select the SSH key that Ansible will use for the lab."""

    configured_key = os.environ.get("MULTIPASS_LAB_SSH_KEY")
    if configured_key:
        candidates = [Path(configured_key).expanduser()]
    else:
        ssh_directory = Path.home() / ".ssh"
        candidates = []
        if INVENTORY_FILE.is_file():
            for line in INVENTORY_FILE.read_text(encoding="utf-8").splitlines():
                key, separator, value = line.partition("=")
                if separator and key.strip() == "ansible_ssh_private_key_file":
                    candidates.append(Path(value.strip().strip("'\"")).expanduser())
                    break
        candidates.extend(
            [ssh_directory / "id_ed25519", ssh_directory / "id_rsa"]
        )

    for private_key in candidates:
        public_key = Path(f"{private_key}.pub")
        if private_key.is_file() and public_key.is_file():
            return private_key.resolve()

    if configured_key:
        raise LabError(
            "The configured private key or its matching .pub file does not exist: "
            f"{candidates[0]}"
        )
    raise LabError(
        "No id_ed25519 or id_rsa SSH key pair found; "
        "set MULTIPASS_LAB_SSH_KEY"
    )


def read_ssh_public_key(private_key: Path) -> str:
    """Read and minimally validate the public key used by cloud-init."""

    public_key = Path(f"{private_key}.pub").read_text(encoding="utf-8").strip()
    if "\n" in public_key:
        raise LabError("The SSH public key must occupy one line")
    if not public_key.startswith(("ssh-ed25519 ", "ssh-rsa ", "ecdsa-sha2-")):
        raise LabError(f"Unsupported SSH public key format: {private_key}.pub")
    return public_key


@contextlib.contextmanager
def cloud_init_file(private_key: Path) -> Iterator[Path]:
    """Create a temporary cloud-init file and remove it after VM creation."""

    public_key = read_ssh_public_key(private_key)
    contents = f"""#cloud-config
users:
  - name: ubuntu
    gecos: Ubuntu
    groups: [adm, sudo]
    shell: /bin/bash
    lock_passwd: true
    sudo: "ALL=(ALL) NOPASSWD:ALL"
    ssh_authorized_keys:
      - {public_key}
ssh_pwauth: false
packages:
  - python3
"""

    descriptor, temporary_name = tempfile.mkstemp(
        prefix="multipass-k3s-cloud-init.", suffix=".yml"
    )
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_file:
            temporary_file.write(contents)
        yield temporary_path
    finally:
        temporary_path.unlink(missing_ok=True)


def instance_exists(instance: Instance) -> bool:
    """Return whether Multipass knows about an instance."""

    result = subprocess.run(
        ["multipass", "info", instance.name],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def instance_is_running(instance: Instance) -> bool:
    """Return whether commands can currently run inside an instance."""

    result = run(
        ["multipass", "exec", instance.name, "--", "true"],
        check=False,
        capture_output=True,
    )
    return result.returncode == 0


def launch_or_start(instance: Instance, cloud_init: Path) -> None:
    """Start an existing instance or launch a missing one."""

    if instance_exists(instance):
        if instance_is_running(instance):
            print(f"Reusing running instance {instance.name}", flush=True)
            return
        print(f"Starting existing instance {instance.name}", flush=True)
        run(["multipass", "start", instance.name])
        return

    print(f"Launching {instance.name}", flush=True)
    run(
        [
            "multipass",
            "launch",
            MULTIPASS_IMAGE,
            "--name",
            instance.name,
            "--cpus",
            str(instance.cpus),
            "--memory",
            instance.memory,
            "--disk",
            instance.disk,
            "--cloud-init",
            str(cloud_init),
            "--timeout",
            "600",
        ]
    )


def start_instances(cloud_init: Path) -> None:
    """Launch or start all instances concurrently."""

    errors: list[Exception] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(INSTANCES)) as pool:
        futures = [
            pool.submit(launch_or_start, instance, cloud_init)
            for instance in INSTANCES
        ]
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as error:  # Preserve errors until all launches finish.
                errors.append(error)

    if errors:
        raise LabError("One or more Multipass instances failed to start") from errors[0]


def instance_ipv4(instance: Instance) -> str:
    """Wait briefly for an instance and return its first IPv4 address."""

    for _ in range(30):
        result = run(
            ["multipass", "exec", instance.name, "--", "hostname", "-I"],
            check=False,
            capture_output=True,
        )
        if result.returncode == 0:
            for address in result.stdout.split():
                if "." in address:
                    return address
        time.sleep(2)

    raise LabError(f"Could not determine an IPv4 address for {instance.name}")


def write_inventory(private_key: Path) -> None:
    """Atomically generate an inventory containing only the lab instances."""

    addresses = {instance.name: instance_ipv4(instance) for instance in INSTANCES}
    ssh_common_args = (
        "-o StrictHostKeyChecking=accept-new "
        f"-o UserKnownHostsFile={KNOWN_HOSTS_FILE}"
    )
    contents = f"""# Generated by scripts/multipass-lab.py; do not edit.
[k3s_control_plane]
{SERVER.name} ansible_host={addresses[SERVER.name]}

[k3s_workers]
{WORKER_ONE.name} ansible_host={addresses[WORKER_ONE.name]}
{WORKER_TWO.name} ansible_host={addresses[WORKER_TWO.name]}

[k3s_cluster:children]
k3s_control_plane
k3s_workers

[all:vars]
ansible_user=ubuntu
ansible_ssh_private_key_file={private_key}
ansible_python_interpreter=/usr/bin/python3
ansible_ssh_common_args='{ssh_common_args}'
"""

    descriptor, temporary_name = tempfile.mkstemp(
        prefix="inventory.multipass.ini.", dir=ANSIBLE_DIR
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_file:
            temporary_file.write(contents)
        temporary_path.replace(INVENTORY_FILE)
    finally:
        temporary_path.unlink(missing_ok=True)

    KNOWN_HOSTS_FILE.write_text("", encoding="utf-8")
    print(f"Generated {INVENTORY_FILE}")


def create_lab() -> None:
    """Create or start the VMs and generate their Ansible inventory."""

    require_multipass()
    private_key = find_ssh_private_key()
    with cloud_init_file(private_key) as cloud_init:
        start_instances(cloud_init)
    write_inventory(private_key)

    print(
        "\nLab ready. Test it with:\n"
        f"  ansible-playbook -i {INVENTORY_FILE} "
        f"{ANSIBLE_DIR / 'distributions.yml'}\n"
        f"  ansible -i {INVENTORY_FILE} k3s_cluster -m ping\n"
        f"  ansible-playbook -i {INVENTORY_FILE} {ANSIBLE_DIR / 'k3s.yml'}"
    )


def show_status() -> None:
    """Show Multipass details for each lab instance."""

    require_multipass()
    for instance in INSTANCES:
        if instance_exists(instance):
            run(["multipass", "info", instance.name])
        else:
            print(f"{instance.name}: missing")


def destroy_lab() -> None:
    """Permanently remove only the named lab instances and generated files."""

    require_multipass()
    for instance in INSTANCES:
        if instance_exists(instance):
            run(["multipass", "delete", "--purge", instance.name])

    INVENTORY_FILE.unlink(missing_ok=True)
    KNOWN_HOSTS_FILE.unlink(missing_ok=True)
    print("Deleted the Multipass k3s lab and its generated local files.")


def parse_arguments() -> argparse.Namespace:
    """Parse the requested lab operation."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("create", "status", "destroy"),
        help="lab operation to perform",
    )
    return parser.parse_args()


def main() -> int:
    """Run the selected lab operation."""

    arguments = parse_arguments()
    operations = {
        "create": create_lab,
        "status": show_status,
        "destroy": destroy_lab,
    }

    try:
        operations[arguments.command]()
    except (LabError, OSError, subprocess.SubprocessError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
