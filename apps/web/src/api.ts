export type PlanStep = {
  name: string;
  status: string;
  detail?: string | null;
};

export type Validation = {
  is_safe: boolean;
  errors: string[];
  warnings: string[];
  tables: string[];
};

export type ChatResponse = {
  answer: string;
  plan: PlanStep[];
  sql?: string | null;
  rows_preview: Record<string, unknown>[];
  columns: string[];
  warnings: string[];
  metadata_version?: string | null;
  validation?: Validation | null;
  requires_execution_approval: boolean;
  executed: boolean;
};

export type Health = {
  status: string;
  llm_configured: boolean;
  nemo_guardrails_enabled: boolean;
  nemo_guardrails_ready: boolean;
  oracle_configured: boolean;
  oracle_reachable: boolean | null;
  metadata_loaded: boolean;
  metadata_version?: string | null;
};

export type UploadResponse = {
  version: string;
  tables: number;
  columns: number;
  relationships: number;
  terms: number;
  metrics: number;
  warnings: string[];
  errors: string[];
};

export type OracleSettings = {
  dsn?: string | null;
  user?: string | null;
  password_set: boolean;
  current_schema?: string | null;
  mode: "thin" | "thick";
  client_lib_dir?: string | null;
  sql_max_rows: number;
  sql_timeout_seconds: number;
  configured: boolean;
};

export type OracleSettingsPayload = {
  dsn?: string | null;
  user?: string | null;
  password?: string | null;
  clear_password?: boolean;
  current_schema?: string | null;
  mode: "thin" | "thick";
  client_lib_dir?: string | null;
  sql_max_rows: number;
  sql_timeout_seconds: number;
};

export type OracleConnectionTest = {
  configured: boolean;
  reachable: boolean | null;
  message: string;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(init?.headers ?? {})
    }
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getHealth(): Promise<Health> {
  return request<Health>("/health");
}

export function sendChat(message: string, sessionId: string): Promise<ChatResponse> {
  return request<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({ message, session_id: sessionId })
  });
}

export function previewSql(message: string): Promise<ChatResponse> {
  return request<ChatResponse>("/sql/preview", {
    method: "POST",
    body: JSON.stringify({ message })
  });
}

export function executeSql(
  message: string,
  sql: string,
  sessionId: string,
  metadataVersion?: string | null
): Promise<ChatResponse> {
  return request<ChatResponse>("/sql/execute", {
    method: "POST",
    body: JSON.stringify({
      message,
      sql,
      session_id: sessionId,
      metadata_version: metadataVersion
    })
  });
}

export function uploadMetadata(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  return request<UploadResponse>("/metadata/upload", {
    method: "POST",
    body: form
  });
}

function adminHeaders(token: string): HeadersInit {
  return token.trim() ? { "X-Setup-Token": token.trim() } : {};
}

export function getOracleSettings(token = ""): Promise<OracleSettings> {
  return request<OracleSettings>("/settings/oracle", {
    headers: adminHeaders(token)
  });
}

export function saveOracleSettings(payload: OracleSettingsPayload, token = ""): Promise<OracleSettings> {
  return request<OracleSettings>("/settings/oracle", {
    method: "POST",
    headers: adminHeaders(token),
    body: JSON.stringify(payload)
  });
}

export function testOracleSettings(payload: OracleSettingsPayload, token = ""): Promise<OracleConnectionTest> {
  return request<OracleConnectionTest>("/settings/oracle/test", {
    method: "POST",
    headers: adminHeaders(token),
    body: JSON.stringify(payload)
  });
}

export function templateUrl(): string {
  return `${API_BASE}/metadata/template`;
}
