import { useEffect, useState } from "react";
import {
  ExternalLink,
  FileText,
  Globe,
  Link2,
  MessageSquare,
  Plug,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import { api } from "../api";

const FUTURE_PLATFORMS = [
  { name: "GitHub", desc: "Auto-sync repo READMEs and release notes into project knowledge." },
  { name: "X / Twitter", desc: "Cross-post engineering threads from the same approved draft." },
  { name: "Gmail / IMAP", desc: "Auto-ingest LinkedIn job-alert emails into the pipeline." },
];

export default function ConnectorsPanel({ onStatusChange }) {
  const [connectors, setConnectors] = useState([]);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState("");

  const load = async () => {
    setConnectors(await api.getConnectors());
    onStatusChange?.();
  };

  useEffect(() => {
    load();
  }, []);

  const connect = async (platform) => {
    setBusy(platform);
    try {
      const res = await api.connectPlatform(platform);
      window.location.href = res.auth_url;
    } catch (err) {
      setMsg(err.message);
      setBusy("");
    }
  };

  const disconnect = async (platform) => {
    setBusy(platform);
    try {
      await api.disconnectPlatform(platform);
      await load();
      setMsg("Account disconnected.");
    } catch (err) {
      setMsg(err.message);
    } finally {
      setBusy("");
    }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <div className="page-eyebrow">
            <Plug size={12} /> Integrations
          </div>
          <h2 className="page-title">Platform connectors</h2>
          <p className="page-sub">
            LinkedIn runs on official OAuth 2.0. Additional platforms plug into the same connector interface
            without changing your workspace.
          </p>
        </div>
        <div className="head-actions">
          <span className="status-pill">
            <ShieldCheck size={13} /> Tokens stored locally, encrypted
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

      {connectors.map((connector) => (
        <section className="connector-card" key={connector.platform}>
          <div className="connector-hd">
            <span className="brand-tile">{connector.display_name?.slice(0, 2).toUpperCase() || "LI"}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="connector-name">{connector.display_name}</div>
              <p className="connector-desc">{connector.description}</p>
            </div>
            <span
              className={`badge ${
                connector.connected ? "ok" : connector.configured ? "warn" : "err"
              }`}
              style={{ flexShrink: 0 }}
            >
              <span className="dot" />
              {connector.connected
                ? `Connected · ${connector.account_label}`
                : connector.configured
                ? "Ready to connect"
                : "Needs client credentials"}
            </span>
          </div>

          <div className="connector-body">
            <div>
              <table className="cap-table">
                <tbody>
                  <tr>
                    <td>
                      <span className="cap-name">
                        <FileText /> Publish posts
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${connector.capabilities?.can_publish_post ? "ok" : "warn"}`}>
                        {connector.capabilities?.can_publish_post ? "Live API" : "Manual fallback"}
                      </span>
                    </td>
                  </tr>
                  <tr>
                    <td>
                      <span className="cap-name">
                        <MessageSquare /> Comments
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${connector.capabilities?.can_comment ? "ok" : "warn"}`}>
                        {connector.capabilities?.can_comment ? "API + fallback" : "Manual fallback"}
                      </span>
                    </td>
                  </tr>
                  <tr>
                    <td>
                      <span className="cap-name">
                        <Globe /> Profile sections
                      </span>
                    </td>
                    <td>
                      <span className="badge warn">Manual paste + copy</span>
                    </td>
                  </tr>
                  <tr>
                    <td>
                      <span className="cap-name">
                        <Search /> Job discovery
                      </span>
                    </td>
                    <td>
                      <span className="badge ok">Live feeds + import</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div>
              <div className="connector-note">
                <strong>Connector notes</strong>
                {connector.capabilities?.notes}
              </div>
              <div className="row" style={{ marginTop: 10 }}>
                {!connector.connected ? (
                  <button
                    className="btn btn-dark btn-block"
                    type="button"
                    disabled={busy === connector.platform}
                    onClick={() => connect(connector.platform)}
                  >
                    <ExternalLink size={14} /> Connect via OAuth
                  </button>
                ) : (
                  <button
                    className="btn btn-block"
                    type="button"
                    disabled={busy === connector.platform}
                    onClick={() => disconnect(connector.platform)}
                  >
                    Disconnect account
                  </button>
                )}
              </div>
            </div>
          </div>
        </section>
      ))}

      <section className="card">
        <div className="card-hd">
          <div>
            <h3 className="card-title">
              <Link2 size={15} /> Extensible platform slots
            </h3>
            <p className="card-desc">Each new connector appears here automatically once registered.</p>
          </div>
          <span className="badge">{FUTURE_PLATFORMS.length} planned</span>
        </div>

        <div className="slot-grid">
          {FUTURE_PLATFORMS.map((platform) => (
            <div className="slot-card" key={platform.name}>
              <div className="slot-hd">
                <span className="slot-name">{platform.name}</span>
                <span className="badge neutral">Slot</span>
              </div>
              <p className="slot-desc">{platform.desc}</p>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
