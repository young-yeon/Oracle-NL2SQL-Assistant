# Project-Contained RHEL9 x86_64 Offline Files

This directory is the local holding area for files that are included in the
final `dist/oracle-nl2sql-project-rhel9-x86_64.tar.gz` transfer archive.

The GitHub repository tracks only the README files here. RPMs, wheels, image
tar files, manifests, and checksums are generated or copied locally and are
ignored by Git.

Current host deployment inputs:

- `wheels/api-py312-linux-amd64/`: Python 3.12 wheelhouse for the FastAPI app.
- `rpms/`: optional RHEL9-compatible RPMs for `python3.12-pip`,
  `python3.12-devel`, and compiler prerequisites when source Python packages
  must be built offline.
- `images/qdrant-v1.12.4-linux-amd64.tar`: optional Qdrant image tar retained
  for future vector-store deployment paths.

Do not install every RPM in `rpms/` on a target server. The host installer
selects only the minimal package subset it needs. Blanket RPM installation can
make `dnf` attempt to replace or remove protected OS packages such as
`systemd`.
