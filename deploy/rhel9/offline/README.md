# Project-Contained RHEL9 x86_64 Offline Files

This directory is intentionally part of the project. It contains the files that the target RHEL9 x86_64 server needs after only `sudo dnf install python3.12` has been prepared.

Included now:

- `rpms/`: Rocky Linux 9 x86_64/noarch RPMs for Podman, Python 3.12 pip tooling, and runtime prerequisites.
- `wheels/host-py312/`: Python 3.12 wheels for `podman-compose`.
- `wheels/api-py312-linux-amd64/`: Python wheels used when building the API image offline.
- `images/qdrant-v1.12.4-linux-amd64.tar`: Qdrant image tar for offline `podman load`.

Required before creating the full project transfer archive:

- `images/python-3.12-linux-amd64.tar`
- `images/nginx-1.27-alpine-linux-amd64.tar`
- `apps/web/dist/index.html`

Prepare those on an internet-connected staging machine:

```bash
./deploy/rhel9/scripts/prepare-offline-build-inputs.sh
```

The project-specific linux/amd64 API and web image tar is generated on the final x86_64 RHEL9 server after the project archive is extracted:

```bash
./deploy/rhel9/scripts/build-linux-amd64-images.sh
```
