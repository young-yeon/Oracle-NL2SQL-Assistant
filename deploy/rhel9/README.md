# RHEL9 x86_64 Offline Project Transfer

This deployment path is for a fully separated on-premises RHEL9-compatible x86_64 server.

The target server only needs this prepared first:

```bash
sudo dnf install python3.12
```

Everything else is included in the project archive.

## Files To Move

Copy these two files to the target server:

```text
dist/oracle-nl2sql-project-rhel9-x86_64.tar.gz
dist/install-oracle-nl2sql-project-rhel9.sh
```

The archive contains:

- application source
- built React web files
- optional RHEL9-compatible x86_64 RPMs for Python build prerequisites
- Python 3.12 API packagehouse
- host deployment scripts
- optional Qdrant image tar

## Run On The Server

```bash
sudo bash install-oracle-nl2sql-project-rhel9.sh oracle-nl2sql-project-rhel9-x86_64.tar.gz
```

The installer:

- extracts the project to `/opt/oracle-nl2sql-project`
- checks Python 3.12 venv/pip support
- installs only minimal offline build RPMs when source Python packages require them
- creates `/opt/oracle-nl2sql/.venv`
- installs Python packages with `pip --no-index`
- serves API and web from one FastAPI/uvicorn service
- installs and starts `oracle-nl2sql.service`
- runs a smoke test

The web UI and API are both served from:

```text
http://<server>:8000
```

## Configuration

Runtime env lives here:

```text
/opt/oracle-nl2sql/.env
```

Oracle settings can also be configured from the web UI.

## Rebuild The Transfer Archive

After changing code or offline files:

```bash
./deploy/rhel9/scripts/create-project-transfer-archive.sh
```

To refresh Python package files:

```bash
python3.12 deploy/rhel9/scripts/prepare-api-python-packages.py
```

To refresh RPMs from Rocky9 repositories:

```bash
./deploy/rhel9/scripts/refresh-offline-rpms-wheels.sh
```

Do not manually run `dnf install deploy/rhel9/offline/rpms/*.rpm` on the target
server. The bundle can contain OS dependency RPMs from Rocky repositories, and
blanket installation can cause protected RHEL packages such as `systemd` to be
replaced or removed. The installer selects only the small RPM subset it needs.

## Notes

- The runtime mode is host venv + systemd, not Podman.
- Container image tar creation is not required for the final server.
- The Oracle database is not deployed by this stack.
- The Oracle user should be read-only.
