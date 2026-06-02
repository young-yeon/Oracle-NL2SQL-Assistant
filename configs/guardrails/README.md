# NeMo Guardrails Configuration

The API service uses this directory as the source template for runtime NeMo Guardrails configuration. At startup, it writes a generated `config.yml` under the storage directory with model settings from environment variables, then loads this directory with `RailsConfig.from_path`.

The active input rail is `self check input`. It is intended to block prompt injection, credential extraction, destructive database requests, and requests outside the Oracle/business-data assistant scope.

