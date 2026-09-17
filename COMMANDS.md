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

## NFS client mounts

The examples below use `192.168.50.10` as the NFS server,
`/export/media` as its exported directory, and `/mnt/nfs/media` as the local
mount point. Replace them with the real values.

### Install the NFS client on Debian or Ubuntu

```bash
sudo apt update
sudo apt install nfs-common
```

### List exports advertised by the server

```bash
showmount -e 192.168.50.10
```

Some NFSv4-only servers do not support export discovery with `showmount`. In
that case, obtain the exported path from the server configuration.

### Create the local mount point

```bash
sudo mkdir -p /mnt/nfs/media
```

The local directory must exist before mounting. Prefer an empty directory:
mounting over a directory temporarily hides its existing contents until the
NFS filesystem is unmounted.

### Mount an NFS export

```bash
sudo mount -t nfs 192.168.50.10:/export/media /mnt/nfs/media
```

The syntax is `SERVER:EXPORTED_PATH LOCAL_MOUNT_POINT`. To request a specific
NFS version:

```bash
sudo mount -t nfs -o nfsvers=4.1 \
  192.168.50.10:/export/media \
  /mnt/nfs/media
```

### Verify the mount

```bash
findmnt /mnt/nfs/media
df -hT /mnt/nfs/media
ls -la /mnt/nfs/media
```

### Unmount the NFS filesystem

First leave the mounted directory, then unmount it by its local path:

```bash
cd ~
sudo umount /mnt/nfs/media
```

If the target is busy, identify the processes using it:

```bash
sudo fuser -vm /mnt/nfs/media
```

If the NFS server is unavailable and a normal unmount remains stuck, a lazy
unmount detaches it from the local directory and cleans it up when no longer in
use:

```bash
sudo umount -l /mnt/nfs/media
```

### Mount automatically through `/etc/fstab`

Add this line to `/etc/fstab`:

```fstab
192.168.50.10:/export/media /mnt/nfs/media nfs defaults,_netdev,nofail,x-systemd.automount 0 0
```

Then validate the configuration without rebooting:

```bash
sudo systemctl daemon-reload
sudo mount -a
ls /mnt/nfs/media
```

- `_netdev` identifies the filesystem as network storage.
- `nofail` allows the computer to boot when the server is unavailable.
- `x-systemd.automount` mounts it when the local directory is accessed.

## Kubernetes Secrets

Kubernetes stores Secret values under `.data` as base64-encoded strings.
Base64 is an encoding, not encryption, so decoded values must still be treated
as credentials.

### List Secrets in a namespace

```bash
kubectl get secrets --namespace argocd
```

### Inspect Secret metadata without decoding its values

```bash
kubectl describe secret argocd-initial-admin-secret --namespace argocd
```

`describe` shows metadata and the names and sizes of stored keys, but it does
not print the credential values.

### View the encoded Secret resource

```bash
kubectl get secret argocd-initial-admin-secret \
  --namespace argocd \
  --output=yaml
```

Values shown beneath `data` are base64-encoded.

### Decode one key from a Secret

```bash
kubectl get secret SECRET_NAME \
  --namespace NAMESPACE \
  --output=jsonpath='{.data.KEY_NAME}' | base64 --decode
printf '\n'
```

Replace `SECRET_NAME`, `NAMESPACE`, and `KEY_NAME`. To see the available key
names without revealing their values:

```bash
kubectl get secret SECRET_NAME \
  --namespace NAMESPACE \
  --output=json | jq --raw-output '.data | keys[]'
```

### Read the initial Argo CD administrator password

```bash
kubectl get secret argocd-initial-admin-secret \
  --namespace argocd \
  --output=jsonpath='{.data.password}' | base64 --decode
printf '\n'
```

The initial username is `admin`. Argo CD may remove
`argocd-initial-admin-secret` after the password is changed, so `NotFound` is
expected later.

### Decode every key in a Secret

```bash
kubectl get secret SECRET_NAME \
  --namespace NAMESPACE \
  --output=json |
  jq --raw-output '.data | to_entries[] | "\(.key)=\(.value | @base64d)"'
```

This prints every credential in the Secret. Avoid running it while screen
sharing, and never paste its output into logs, chat, shell scripts, or Git.
