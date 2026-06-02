# Optional Container Image Tar Files

The final RHEL9 deployment path runs the app as a host `systemd` service, so it
does not require Podman image tar files.

`qdrant-v1.12.4-linux-amd64.tar` can still be placed here when an offline
Qdrant/vector-store deployment path is needed later. The file is intentionally
ignored by Git and should be carried in the generated `dist/` transfer archive,
not in the GitHub repository.
