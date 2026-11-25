import { useEffect, useState } from "react";
import { AlertTriangle, Check, Cpu, ShieldCheck, Sparkles, X } from "lucide-react";
import { api } from "../api";

export default function SettingsPanel({ onSaved }) {
  const [cfg, setCfg] = useState(null);
  const [apiKey, setApiKey] = useState("");
  const [hfToken, setHfToken] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setCfg(await api.getSettings());
  };

  useEffect(() => {
    load();
  }, []);

  const save = async (event) => {
    event.preventDefault();
    setBusy(true);
    const payload = {
      ai_provider: cfg.ai_provider,
      ollama_base_url: cfg.ollama_base_url,
      ollama_model: cfg.ollama_model,
      external_ai_base_url: cfg.external_ai_base_url,
      external_ai_model: cfg.external_ai_model,
    };
    if (apiKey.trim()) payload.external_ai_api_key = apiKey.trim();
    if (hfToken.trim()) payload.hf_token = hfToken.trim();
    try {
      const updated = await api.updateSettings(payload);
      setCfg(updated);
      setApiKey("");
      setHfToken("");
      setMsg("AI and privacy settings saved.");
      onSaved?.();
    } catch (err) {
      setMsg(err.message);
    } finally {
      setBusy(false);
    }
  };

  if (!cfg) return <p className="muted">Loading settings…</p>;

  return (
    <>
      <div className="page-head">
        <div>
          <div className="page-eyebrow">
            <ShieldCheck size={12} /> System
          </div>
          <h2 className="page-title">AI &amp; privacy</h2>
          <p className="page-sub">
            Run entirely on your machine with Ollama, or connect an external OpenAI-compatible endpoint.
            Your CV and notes only leave the laptop if you choose external mode.
          </p>
        </div>
        <div className="head-actions">
          <span className={`badge ${cfg.is_external ? "warn" : "ok"}`}>
            <span className="dot" /> {cfg.is_external ? "External API active" : "Local only"}
          </span>
        </div>
      </div>

      {msg && (
        <div className="banner">
          <span>{msg}</span>
          <button type="button" className="banner-close" onClick={() => setMsg("")} aria-label="Dismiss">
            <X size={14} />
          </button>
        </div>
      )}

      <form className="card" onSubmit={save}>
        <div className="settings-section">
          <div className="card-hd">
            <div>
              <h3 className="card-title">
                <Cpu size={15} /> Model provider
              </h3>
              <p className="card-desc">Choose where drafting requests are processed.</p>
            </div>
          </div>

          <div className="radio-grid">
            <button
              type="button"
              className={`radio-card ${cfg.ai_provider === "ollama" ? "active" : ""}`}
              onClick={() => setCfg({ ...cfg, ai_provider: "ollama" })}
            >
              <span className="radio-mark" />
              <span>
                <span className="radio-title">
                  Local Ollama <span className="badge mint">Free</span>
                </span>
                <span className="radio-desc">Private, offline-capable and 100% free on your laptop.</span>
              </span>
            </button>

            <button
              type="button"
              className={`radio-card ${cfg.ai_provider === "external" ? "active" : ""}`}
              onClick={() => setCfg({ ...cfg, ai_provider: "external" })}
            >
              <span className="radio-mark" />
              <span>
                <span className="radio-title">
                  External API <span className="badge">Optional</span>
                </span>
                <span className="radio-desc">Any OpenAI-compatible endpoint with your own key.</span>
              </span>
            </button>
          </div>

          {cfg.ai_provider === "ollama" ? (
            <>
              <div className="status-line" style={{ marginBottom: 12 }}>
                <span className="row" style={{ gap: 7 }}>
                  <span className="dot" style={{ background: cfg.ollama_status?.running ? "var(--green)" : "var(--pebble)" }} />
                  <strong>Ollama daemon</strong>
                </span>
                <span className={`badge ${cfg.ollama_status?.running ? "ok" : "err"}`}>
                  {cfg.ollama_status?.running
                    ? `Running · ${(cfg.ollama_status.models || []).length} models`
                    : "Not running"}
                </span>
              </div>
              {!cfg.ollama_status?.running && (
                <div className="notice">
                  <AlertTriangle />
                  <span>Start Ollama on Windows (`ollama serve`) or open the tray app, then reload.</span>
                </div>
              )}
              <div className="field-grid">
                <div className="field">
                  <label className="field-label">Ollama base URL</label>
                  <input
                    value={cfg.ollama_base_url || ""}
                    onChange={(event) => setCfg({ ...cfg, ollama_base_url: event.target.value })}
                  />
                </div>
                <div className="field">
                  <label className="field-label">Model</label>
                  <input
                    value={cfg.ollama_model || ""}
                    onChange={(event) => setCfg({ ...cfg, ollama_model: event.target.value })}
                  />
                </div>
              </div>
              {(cfg.ollama_status?.models || []).length > 0 && (
                <p className="model-list">Installed: {cfg.ollama_status.models.join(" · ")}</p>
              )}
            </>
          ) : (
            <>
              <div className="notice">
                <AlertTriangle />
                <span>
                  External transmission notice: CV excerpts, project notes and job descriptions are sent to the
                  endpoint below.
                </span>
              </div>
              <div className="field-grid">
                <div className="field">
                  <label className="field-label">Base URL</label>
                  <input
                    value={cfg.external_ai_base_url || ""}
                    onChange={(event) => setCfg({ ...cfg, external_ai_base_url: event.target.value })}
                    placeholder="https://api.openai.com/v1"
                  />
                </div>
                <div className="field">
                  <label className="field-label">Model</label>
                  <input
                    value={cfg.external_ai_model || ""}
                    onChange={(event) => setCfg({ ...cfg, external_ai_model: event.target.value })}
                    placeholder="gpt-4o-mini"
                  />
                </div>
                <div className="field span-2">
                  <label className="field-label">
                    API key {cfg.has_external_api_key ? "(saved — enter to replace)" : ""}
                  </label>
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(event) => setApiKey(event.target.value)}
                    placeholder="sk-…"
                    autoComplete="off"
                  />
                </div>
              </div>
            </>
          )}
        </div>

        <div className="settings-section">
          <div className="card-hd">
            <div>
              <h3 className="card-title">
                <Sparkles size={15} /> Photorealistic Image Generation
              </h3>
              <p className="card-desc">
                Optional free Hugging Face token for FLUX.1-schnell (~5-10+ photorealistic images/day). Falls back to
                free Pollinations FLUX if empty.
              </p>
            </div>
          </div>
          <div className="field">
            <label className="field-label">
              Hugging Face token {cfg.has_hf_token ? "(saved — enter to replace)" : "(optional, free)"}
            </label>
            <input
              type="password"
              value={hfToken}
              onChange={(event) => setHfToken(event.target.value)}
              placeholder="hf_… (from huggingface.co/settings/tokens)"
              autoComplete="off"
            />
          </div>
        </div>

        <div className="settings-section">
          <h3 className="card-title" style={{ marginBottom: 10 }}>
            <ShieldCheck size={15} /> Data handling
          </h3>
          <div className="status-line" style={{ marginBottom: 8 }}>
            <span>Storage</span>
            <strong className="mono">data/app.db · local SQLite</strong>
          </div>
          <div className="status-line" style={{ marginBottom: 8 }}>
            <span>LinkedIn tokens</span>
            <strong>Encrypted locally</strong>
          </div>
          <div className="status-line">
            <span>Publishing</span>
            <strong>Always requires explicit approval</strong>
          </div>
        </div>

        <div className="form-actions">
          <button className="btn btn-dark" type="submit" disabled={busy}>
            <Check size={14} /> {busy ? "Saving…" : "Save configuration"}
          </button>
          <button className="btn" type="button" onClick={load} disabled={busy}>
            <Sparkles size={14} /> Reload status
          </button>
        </div>
      </form>
    </>
  );
}
