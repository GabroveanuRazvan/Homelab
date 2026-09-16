# Homelab CLI cheat sheet

Run these examples from the repository root unless a command says otherwise.

## Ansible

### Ping every host in a specific inventory

```bash
ansible -i ansible/inventory.ini all -m ansible.builtin.ping
```

- `ansible` runs a one-off command instead of a playbook.
- `-i ansible/inventory.ini` selects the inventory file explicitly.
- `all` selects every host in that inventory. Replace it with a group such as
  `k3s_cluster` or a host such as `mini-pc` to narrow the target.
- `-m ansible.builtin.ping` runs Ansible's ping module. It verifies SSH access
  and that Ansible can execute Python on the remote host; it is not an ICMP
  network ping.

## SSH

### Generate a dedicated SSH key for the homelab

```bash
ssh-keygen -t ed25519 -a 100 -C "homelab-ansible" -f ~/.ssh/homelab_ansible
```

- `-t ed25519` selects the modern Ed25519 key algorithm.
- `-a 100` strengthens passphrase processing by using 100 derivation rounds.
- `-C "homelab-ansible"` adds a label that helps identify the public key.
- `-f ~/.ssh/homelab_ansible` selects the output path. The private key is
  `~/.ssh/homelab_ansible` and the shareable public key is
  `~/.ssh/homelab_ansible.pub`.

Do not share the private key. `ssh-keygen` will ask whether to protect it with
a passphrase. Also, choose a different filename if that path already exists;
confirming an overwrite would replace the existing key.

### Copy the public key to a host

```bash
ssh-copy-id -i ~/.ssh/homelab_ansible.pub razvan@mini-pc.home
```

This logs in with the user's current password and adds the public key to the
remote user's `~/.ssh/authorized_keys`. Replace the username and hostname for
other machines.

### Test key-based SSH access

```bash
ssh -i ~/.ssh/homelab_ansible razvan@mini-pc.home
```

The `-i` option explicitly selects the private identity file.

### Tell Ansible to use the dedicated key

Add this beneath `[all:vars]` in `ansible/inventory.ini`:

```ini
ansible_ssh_private_key_file=~/.ssh/homelab_ansible
```

Then verify every inventory host:

```bash
ansible -i ansible/inventory.ini all -m ansible.builtin.ping
```

## Symbolic links

### Create a symbolic link

```bash
ln -s /path/to/real-file ~/shortcut
```

The first path is the existing target; the second is the new link name. The
same command works for directories:

```bash
ln -s /srv/homelab-data ~/homelab-data
```

### Inspect a symbolic link

```bash
ls -l ~/shortcut
readlink ~/shortcut
readlink -f ~/shortcut
```

`readlink` prints the target stored in the link. `readlink -f` resolves the
complete absolute path, including any other links in the path.

### Replace an existing symbolic link

```bash
ln -sfnT /path/to/new-target ~/shortcut
```

- `-s` creates a symbolic link.
- `-f` replaces the existing destination.
- `-n` avoids following an existing link to a directory.
- `-T` always treats `~/shortcut` as the link name rather than as a directory.

Use this only after checking the existing destination with `ls -ld`, because
`-f` replaces it.

### Remove a symbolic link

```bash
unlink ~/shortcut
```

Alternatively:

```bash
rm -- ~/shortcut
```

Both commands remove the link itself, not the target. Do not append `/` to a
symlink-to-directory path when removing it.
