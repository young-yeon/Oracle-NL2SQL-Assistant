import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Database,
  Download,
  FileSpreadsheet,
  KeyRound,
  Loader2,
  PanelRight,
  PlugZap,
  RefreshCw,
  Save,
  Search,
  Send,
  ShieldCheck,
  Upload
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  ChatResponse,
  executeSql,
  getHealth,
  getOracleSettings,
  Health,
  OracleSettings,
  OracleSettingsPayload,
  previewSql,
  saveOracleSettings,
  sendChat,
  templateUrl,
  testOracleSettings,
  uploadMetadata
} from "./api";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

type OracleFormState = {
  dsn: string;
  user: string;
  password: string;
  clearPassword: boolean;
  current_schema: string;
  mode: "thin" | "thick";
  client_lib_dir: string;
  sql_max_rows: number;
  sql_timeout_seconds: number;
};

const starterResponse: ChatResponse = {
  answer: "Upload metadata, then ask a read-only Oracle data question.",
  plan: [],
  rows_preview: [],
  columns: [],
  warnings: [],
  requires_execution_approval: false,
  executed: false
};

const defaultOracleForm: OracleFormState = {
  dsn: "",
  user: "",
  password: "",
  clearPassword: false,
  current_schema: "",
  mode: "thin",
  client_lib_dir: "/opt/oracle/instantclient",
  sql_max_rows: 100,
  sql_timeout_seconds: 30
};

function createId(): string {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }
  const random = typeof globalThis.crypto?.getRandomValues === "function"
    ? Array.from(globalThis.crypto.getRandomValues(new Uint32Array(4)))
        .map((value) => value.toString(16).padStart(8, "0"))
        .join("")
    : `${Date.now().toString(16)}${Math.random().toString(16).slice(2)}`;
  return `id-${random}`;
}

function statusLabel(value: boolean | null | undefined): string {
  if (value === true) return "ready";
  if (value === false) return "missing";
  return "not set";
}

function statusClass(value: string): string {
  if (value === "ready") return "ok";
  if (value === "failed" || value === "missing") return "warn";
  return "muted";
}

function nemoStatusLabel(health?: Health | null): string {
  if (health?.nemo_guardrails_ready) return "ready";
  if (health?.nemo_guardrails_enabled && !health.llm_configured) return "waiting LLM";
  return health?.nemo_guardrails_enabled ? "missing" : "off";
}

function oracleStatusLabel(health?: Health | null): string {
  if (health?.oracle_reachable === true) return "ready";
  if (health?.oracle_reachable === false) return "failed";
  return health?.oracle_configured ? "not tested" : "missing";
}

function settingsToForm(settings: OracleSettings): OracleFormState {
  return {
    dsn: settings.dsn ?? "",
    user: settings.user ?? "",
    password: "",
    clearPassword: false,
    current_schema: settings.current_schema ?? "",
    mode: settings.mode,
    client_lib_dir: settings.client_lib_dir ?? "/opt/oracle/instantclient",
    sql_max_rows: settings.sql_max_rows,
    sql_timeout_seconds: settings.sql_timeout_seconds
  };
}

function formToPayload(form: OracleFormState): OracleSettingsPayload {
  return {
    dsn: form.dsn,
    user: form.user,
    password: form.password.trim() ? form.password : null,
    clear_password: form.clearPassword,
    current_schema: form.current_schema,
    mode: form.mode,
    client_lib_dir: form.client_lib_dir,
    sql_max_rows: form.sql_max_rows,
    sql_timeout_seconds: form.sql_timeout_seconds
  };
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "I can turn metadata-backed business questions into read-only Oracle SQL."
    }
  ]);
  const [input, setInput] = useState("");
  const [sessionId] = useState(() => createId());
  const [lastResponse, setLastResponse] = useState<ChatResponse>(starterResponse);
  const [lastSqlQuestion, setLastSqlQuestion] = useState("");
  const [isBusy, setIsBusy] = useState(false);
  const [uploadState, setUploadState] = useState<string>("No metadata uploaded");
  const [oracleForm, setOracleForm] = useState<OracleFormState>(defaultOracleForm);
  const [adminToken, setAdminToken] = useState("");
  const [oracleSettings, setOracleSettings] = useState<OracleSettings | null>(null);
  const [oracleSettingsState, setOracleSettingsState] = useState("Oracle settings not loaded");
  const [isSettingsBusy, setIsSettingsBusy] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(null));
    loadOracleSettings("");
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const healthItems = useMemo(
    () => [
      { label: "LLM", value: statusLabel(health?.llm_configured), icon: Bot },
      { label: "NeMo", value: nemoStatusLabel(health), icon: ShieldCheck },
      { label: "Oracle", value: oracleStatusLabel(health), icon: Database },
      { label: "Metadata", value: statusLabel(health?.metadata_loaded), icon: FileSpreadsheet }
    ],
    [health]
  );
  const oracleConnectionStatus = oracleStatusLabel(health);

  function updateOracleForm<K extends keyof OracleFormState>(key: K, value: OracleFormState[K]) {
    setOracleForm((current) => ({ ...current, [key]: value }));
  }

  async function refreshHealth() {
    try {
      setHealth(await getHealth());
    } catch {
      setHealth(null);
    }
  }

  async function loadOracleSettings(token = adminToken) {
    setIsSettingsBusy(true);
    try {
      const settings = await getOracleSettings(token);
      setOracleSettings(settings);
      setOracleForm(settingsToForm(settings));
      setOracleSettingsState(settings.configured ? "Oracle settings loaded" : "Oracle settings empty");
    } catch (error) {
      setOracleSettingsState(error instanceof Error ? error.message : "Could not load Oracle settings");
    } finally {
      setIsSettingsBusy(false);
    }
  }

  async function handleOracleTest() {
    setIsSettingsBusy(true);
    setOracleSettingsState("Testing Oracle connection");
    try {
      const result = await testOracleSettings(formToPayload(oracleForm), adminToken);
      setOracleSettingsState(result.message);
      await refreshHealth();
    } catch (error) {
      setOracleSettingsState(error instanceof Error ? error.message : "Oracle connection test failed");
    } finally {
      setIsSettingsBusy(false);
    }
  }

  async function handleOracleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSettingsBusy(true);
    setOracleSettingsState("Saving Oracle settings");
    try {
      const saved = await saveOracleSettings(formToPayload(oracleForm), adminToken);
      setOracleSettings(saved);
      setOracleForm(settingsToForm(saved));
      setOracleSettingsState(saved.configured ? "Oracle settings saved" : "Oracle settings saved, but incomplete");
      await refreshHealth();
    } catch (error) {
      setOracleSettingsState(error instanceof Error ? error.message : "Could not save Oracle settings");
    } finally {
      setIsSettingsBusy(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = input.trim();
    if (!message || isBusy) return;

    setInput("");
    setIsBusy(true);
    setLastSqlQuestion(message);
    setMessages((current) => [...current, { id: createId(), role: "user", content: message }]);
    try {
      const response = await sendChat(message, sessionId);
      setLastResponse(response);
      setMessages((current) => [
        ...current,
        { id: createId(), role: "assistant", content: response.answer }
      ]);
      getHealth().then(setHealth).catch(() => undefined);
    } catch (error) {
      const content = error instanceof Error ? error.message : "Request failed.";
      setMessages((current) => [...current, { id: createId(), role: "assistant", content }]);
    } finally {
      setIsBusy(false);
    }
  }

  async function handlePreview() {
    const message = input.trim();
    if (!message || isBusy) return;
    setIsBusy(true);
    setLastSqlQuestion(message);
    try {
      const response = await previewSql(message);
      setLastResponse(response);
    } finally {
      setIsBusy(false);
    }
  }

  async function handleExecuteSql() {
    if (!lastResponse.sql || !lastResponse.validation?.is_safe || isBusy) return;
    const message = lastSqlQuestion || input.trim() || "Approved SQL execution";
    setIsBusy(true);
    setMessages((current) => [
      ...current,
      { id: createId(), role: "user", content: "Approve and execute the validated SQL." }
    ]);
    try {
      const response = await executeSql(message, lastResponse.sql, sessionId, lastResponse.metadata_version);
      setLastResponse(response);
      setMessages((current) => [
        ...current,
        { id: createId(), role: "assistant", content: response.answer }
      ]);
      await refreshHealth();
    } catch (error) {
      const content = error instanceof Error ? error.message : "SQL execution failed.";
      setMessages((current) => [...current, { id: createId(), role: "assistant", content }]);
    } finally {
      setIsBusy(false);
    }
  }

  async function handleFileChange(file?: File | null) {
    if (!file) return;
    setIsBusy(true);
    setUploadState(`Uploading ${file.name}`);
    try {
      const result = await uploadMetadata(file);
      setUploadState(
        result.errors.length
          ? `Import failed: ${result.errors.join(", ")}`
          : `Metadata ${result.version}: ${result.tables} tables, ${result.columns} columns`
      );
      getHealth().then(setHealth).catch(() => undefined);
    } catch (error) {
      setUploadState(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setIsBusy(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <Database size={22} />
          <div>
            <strong>Oracle NL2SQL</strong>
            <span>On-prem assistant</span>
          </div>
        </div>

        <div className="status-list">
          {healthItems.map((item) => (
            <div className="status-row" key={item.label}>
              <item.icon size={16} />
              <span>{item.label}</span>
              <strong className={statusClass(item.value)}>{item.value}</strong>
            </div>
          ))}
        </div>

        <details className="settings-dropdown">
          <summary className="settings-summary">
            <Database size={16} />
            <span>Oracle connection</span>
            <strong className={statusClass(oracleConnectionStatus)}>{oracleConnectionStatus}</strong>
          </summary>
          <form className="oracle-settings" onSubmit={handleOracleSave}>
            <div className="tool-heading">
              <span>{oracleSettingsState}</span>
              <button type="button" className="mini-icon" onClick={() => loadOracleSettings()} disabled={isSettingsBusy} title="Reload settings">
                <RefreshCw size={14} />
              </button>
            </div>
            <label>
              <span>Admin token</span>
              <div className="input-with-icon">
                <KeyRound size={14} />
                <input
                  type="password"
                  value={adminToken}
                  onChange={(event) => setAdminToken(event.target.value)}
                  placeholder="Optional"
                />
              </div>
            </label>
            <label>
              <span>DSN</span>
              <input
                value={oracleForm.dsn}
                onChange={(event) => updateOracleForm("dsn", event.target.value)}
                placeholder="host:1521/ORCLPDB1"
              />
            </label>
            <label>
              <span>User</span>
              <input
                value={oracleForm.user}
                onChange={(event) => updateOracleForm("user", event.target.value)}
                placeholder="readonly_user"
              />
            </label>
            <label>
              <span>Password</span>
              <input
                type="password"
                value={oracleForm.password}
                onChange={(event) => updateOracleForm("password", event.target.value)}
                placeholder={oracleSettings?.password_set ? "Saved password" : "Password"}
              />
            </label>
            {oracleSettings?.password_set && (
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={oracleForm.clearPassword}
                  onChange={(event) => updateOracleForm("clearPassword", event.target.checked)}
                />
                <span>Clear saved password</span>
              </label>
            )}
            <label>
              <span>Schema</span>
              <input
                value={oracleForm.current_schema}
                onChange={(event) => updateOracleForm("current_schema", event.target.value)}
                placeholder="APP"
              />
            </label>
            <div className="settings-grid">
              <label>
                <span>Mode</span>
                <select
                  value={oracleForm.mode}
                  onChange={(event) => updateOracleForm("mode", event.target.value as "thin" | "thick")}
                >
                  <option value="thin">thin</option>
                  <option value="thick">thick</option>
                </select>
              </label>
              <label>
                <span>Rows</span>
                <input
                  type="number"
                  min={1}
                  max={5000}
                  value={oracleForm.sql_max_rows}
                  onChange={(event) => updateOracleForm("sql_max_rows", Number(event.target.value))}
                />
              </label>
            </div>
            <label>
              <span>Client lib</span>
              <input
                value={oracleForm.client_lib_dir}
                onChange={(event) => updateOracleForm("client_lib_dir", event.target.value)}
                disabled={oracleForm.mode === "thin"}
              />
            </label>
            <label>
              <span>Timeout seconds</span>
              <input
                type="number"
                min={1}
                max={600}
                value={oracleForm.sql_timeout_seconds}
                onChange={(event) => updateOracleForm("sql_timeout_seconds", Number(event.target.value))}
              />
            </label>
            <div className="settings-actions">
              <button type="button" onClick={handleOracleTest} disabled={isSettingsBusy}>
                <PlugZap size={15} />
                Test
              </button>
              <button type="submit" disabled={isSettingsBusy}>
                <Save size={15} />
                Save
              </button>
            </div>
          </form>
        </details>

        <div className="metadata-tools">
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx,.xls"
            onChange={(event) => handleFileChange(event.target.files?.[0])}
          />
          <button type="button" onClick={() => fileInputRef.current?.click()} disabled={isBusy}>
            <Upload size={16} />
            Upload metadata
          </button>
          <a className="button-link" href={templateUrl()}>
            <Download size={16} />
            Template
          </a>
          <p>{uploadState}</p>
        </div>

        <div className="session-list">
          <span>Sessions</span>
          <button type="button" className="session-button active">
            Current session
          </button>
        </div>
      </aside>

      <section className="chat-column">
        <div className="chat-header">
          <div>
            <h1>Read-only Oracle data chat</h1>
            <p>Ask with business terms from the uploaded metadata workbook.</p>
          </div>
          <PanelRight size={20} />
        </div>

        <div className="messages">
          {messages.map((message) => (
            <article className={`message ${message.role}`} key={message.id}>
              <div className="avatar">{message.role === "assistant" ? <Bot size={18} /> : <span>U</span>}</div>
              <p>{message.content}</p>
            </article>
          ))}
          {isBusy && (
            <article className="message assistant">
              <div className="avatar">
                <Loader2 className="spin" size={18} />
              </div>
              <p>Working through guardrails, metadata, SQL validation, or approved execution.</p>
            </article>
          )}
          <div ref={bottomRef} />
        </div>

        <form className="composer" onSubmit={handleSubmit}>
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask a read-only Oracle data question..."
          />
          <button type="button" className="icon-button" onClick={handlePreview} disabled={isBusy || !input.trim()} title="Preview SQL">
            <Search size={18} />
          </button>
          <button type="submit" className="send-button" disabled={isBusy || !input.trim()}>
            <Send size={18} />
            Send
          </button>
        </form>
      </section>

      <aside className="details-panel">
        <div className="panel-section">
          <h2>Execution plan</h2>
          <div className="plan-list">
            {lastResponse.plan.length === 0 ? (
              <p className="empty">No run yet.</p>
            ) : (
              lastResponse.plan.map((step) => (
                <div className="plan-row" key={`${step.name}-${step.status}`}>
                  {step.status === "complete" ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
                  <div>
                    <strong>{step.name}</strong>
                    {step.detail && <span>{step.detail}</span>}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="panel-section">
          <h2>SQL</h2>
          <pre className="sql-box">{lastResponse.sql || "No SQL generated."}</pre>
          {lastResponse.validation && (
            <div className={lastResponse.validation.is_safe ? "validation ok-box" : "validation warn-box"}>
              {lastResponse.validation.is_safe ? "SQL passed read-only validation." : "SQL failed validation."}
            </div>
          )}
          {lastResponse.sql && lastResponse.validation?.is_safe && !lastResponse.executed && (
            <div className="approval-box">
              <span>Execution requires explicit approval.</span>
              <button
                type="button"
                onClick={handleExecuteSql}
                disabled={isBusy || !health?.oracle_configured}
              >
                <PlugZap size={15} />
                Execute SQL
              </button>
            </div>
          )}
        </div>

        <div className="panel-section">
          <h2>Warnings</h2>
          {lastResponse.warnings.length === 0 ? (
            <p className="empty">No warnings.</p>
          ) : (
            <ul className="warning-list">
              {lastResponse.warnings.map((warning, index) => (
                <li key={`${warning}-${index}`}>{warning}</li>
              ))}
            </ul>
          )}
        </div>

        <div className="panel-section">
          <h2>Rows preview</h2>
          <div className="table-wrap">
            {lastResponse.rows_preview.length === 0 ? (
              <p className="empty">No rows.</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    {lastResponse.columns.map((column) => (
                      <th key={column}>{column}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {lastResponse.rows_preview.slice(0, 8).map((row, index) => (
                    <tr key={index}>
                      {lastResponse.columns.map((column) => (
                        <td key={column}>{String(row[column] ?? "")}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </aside>
    </main>
  );
}
