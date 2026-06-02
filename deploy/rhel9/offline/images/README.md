# Container Image Tar Files

This directory is copied into the offline RHEL9 bundle and loaded with `podman load`.

Already included:

```text
qdrant-v1.12.4-linux-amd64.tar
```

Required before creating the full project transfer archive:

```text
python-3.12-linux-amd64.tar
nginx-1.27-alpine-linux-amd64.tar
```

Generated on the target x86_64 server after the project is transferred:

```text
oracle-nl2sql-app-images-0.1.0-linux-amd64.tar
```

Prepare missing offline build inputs on an internet-connected staging machine:

```bash
./deploy/rhel9/scripts/prepare-offline-build-inputs.sh
```

Build the app image tar on the final x86_64 RHEL9 server:

```bash
./deploy/rhel9/scripts/build-linux-amd64-images.sh
```

It cannot be generated on the current ARM64 WSL/Docker environment because linux/amd64 containers do not execute there.
