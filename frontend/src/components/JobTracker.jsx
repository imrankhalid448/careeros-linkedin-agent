import { useEffect, useState } from "react";
import {
  Briefcase,
  Check,
  ChevronDown,
  ChevronUp,
  Copy,
  ExternalLink,
  Radio,
  Sparkles,
  Target,
  X,
} from "lucide-react";
import { api } from "../api";
import { prettyStatus, relativeTime, scoreTone, statusTone } from "../utils";
import JobDiscovery from "./JobDiscovery";

const STATUSES = ["Saved", "Preparing", "Applied", "Interview", "Offer", "Rejected"];
const STATUS_DOT = {
  Saved: "var(--pebble)",
  Preparing: "var(--lavender)",
  Applied: "var(--blue)",
  Interview: "var(--tangerine)",
  Offer: "var(--green)",
  Rejected: "#ef4444",
};

export default function JobTracker({ onChanged }) {
  const [jobs, setJobs] = useState([]);
  const [view, setView] = useState("pipeline");
  const [filterStatus, setFilterStatus] = useState("All");
  const [form, setForm] = useState({ raw_text: "", apply_url: "", source_type: "pasted" });
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState("");
  const [copiedId, setCopiedId] = useState("");
  const [showImport, setShowImport] = useState(false);

  const load = async () => {
    setJobs(await api.getJobs());
  };

  useEffect(() => {
    load();
  }, []);

  const refreshAll = () => {
    load();
    onChanged?.();
  };

  const importJob = async (event) => {
    event.preventDefault();
    setBusy(true);
    setMsg("Importing the role and evaluating fit against your CV…");
    try {
      const res = await api.importJob(form);
      setForm({ raw_text: "", apply_url: "", source_type: "pasted" });
      setShowImport(false);
      setMsg(res.warning || "Job assessed and added to your pipeline.");
      refreshAll();
    } catch (err) {
      setMsg(err.message);
    } finally {
      setBusy(false);
    }
  };

  const prepare = async (job) => {
    setBusy(true);
    setMsg(`Preparing a tailored application package for ${job.title}…`);
    try {
      await api.prepareJob(job.id);
      setMsg("Tailored CV edits, cover letter and screening answers saved.");
      refreshAll();
    } catch (err) {
      setMsg(err.message);
    } finally {
      setBusy(false);
    }
  };

  const updateStatus = async (job, status) => {
    try {
      await api.updateJobStatus(job.id, status);
      refreshAll();
    } catch (err) {
      setMsg(err.message);
    }
  };

  const filtered = filterStatus === "All" ? jobs : jobs.filter((job) => job.status === filterStatus);

  return (
    <>
      <div className="page-head">
        <div>
          <div className="page-eyebrow">
            <Briefcase size={12} /> Pipeline
          </div>
          <h2 className="page-title">Jobs &amp; applications</h2>
          <p className="page-sub">
            {view === "pipeline"
              ? "Evidence-backed fit scoring for AI, ML, computer vision and generative AI roles, with tailored application packages prepared by the agent."
              : "Live openings from public job feeds, ranked against your target roles and skills — track any role straight into your pipeline."}
          </p>
        </div>
        <div className="head-actions">
          <div className="segmented">
            <button
              type="button"
              className={view === "pipeline" ? "active" : ""}
              onClick={() => setView("pipeline")}
            >
              <Briefcase /> Pipeline
            </button>
            <button
              type="button"
              className={view === "discover" ? "active" : ""}
              onClick={() => setView("discover")}
            >
              <Radio /> Live jobs
            </button>
          </div>
          <button
            type="button"
            className="btn btn-dark"
            onClick={() => {
              setView("pipeline");
              setShowImport((value) => !value);
            }}
          >
            <Briefcase size={14} /> {showImport && view === "pipeline" ? "Close import" : "Import job"}
          </button>
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

      {view === "discover" ? (
        <JobDiscovery pipelineJobs={jobs} onTracked={refreshAll} />
      ) : (
        <>
          <div className="filter-stats">
            {STATUSES.map((status) => {
              const count = jobs.filter((job) => job.status === status).length;
              return (
                <button
                  type="button"
                  key={status}
                  className={`filter-stat ${filterStatus === status ? "active" : ""}`}
                  onClick={() => setFilterStatus(filterStatus === status ? "All" : status)}
                >
                  <span className="filter-stat-label">
                    <span className="dot" style={{ background: STATUS_DOT[status] }} />
                    {status}
                  </span>
                  <span className="filter-stat-value">{count}</span>
                </button>
              );
            })}
          </div>

          {showImport && (
            <form className="card" onSubmit={importJob} style={{ marginBottom: 12 }}>
              <div className="card-hd">
                <div>
                  <h3 className="card-title">
                    <Briefcase size={15} /> Import an opportunity
                  </h3>
                  <p className="card-desc">
                    Paste a listing, a job-alert email, or a fetchable career page URL.
                  </p>
                </div>
                <button type="button" className="btn btn-sm" onClick={() => setShowImport(false)}>
                  Cancel
                </button>
              </div>

              <div className="field-grid">
                <div className="field">
                  <label className="field-label">Source type</label>
                  <select
                    value={form.source_type}
                    onChange={(event) => setForm({ ...form, source_type: event.target.value })}
                  >
                    <option value="pasted">Pasted job listing</option>
                    <option value="email">LinkedIn job-alert email</option>
                    <option value="url">Employer career page URL</option>
                  </select>
                </div>
                <div className="field">
                  <label className="field-label">Application / career page URL</label>
                  <input
                    value={form.apply_url}
                    onChange={(event) => setForm({ ...form, apply_url: event.target.value })}
                    placeholder="https://…"
                  />
                </div>
                <div className="field span-2">
                  <label className="field-label">Job description / email text</label>
                  <textarea
                    value={form.raw_text}
                    onChange={(event) => setForm({ ...form, raw_text: event.target.value })}
                    placeholder="Paste the job listing or LinkedIn job-alert email text…"
                  />
                </div>
              </div>

              <button className="btn btn-dark" type="submit" disabled={busy}>
                <Sparkles size={14} /> {busy ? "Assessing…" : "Import & assess fit"}
              </button>
            </form>
          )}

          <section className="card">
            <div className="job-toolbar">
              <div>
                <h3 className="card-title">
                  <Target size={15} /> {filterStatus === "All" ? "All opportunities" : `${filterStatus} roles`}
                </h3>
                <p className="card-desc">
                  {filtered.length} {filtered.length === 1 ? "role" : "roles"} · click a row for fit evidence and
                  application drafts.
                </p>
              </div>
              {filterStatus !== "All" && (
                <button type="button" className="link-btn" onClick={() => setFilterStatus("All")}>
                  Clear filter <X />
                </button>
              )}
            </div>

            <div className="table-wrap">
              <table className="data job-table">
                <thead>
                  <tr>
                    <th>Role</th>
                    <th>Location</th>
                    <th>Fit</th>
                    <th>Sponsorship</th>
                    <th>Status</th>
                    <th className="nowrap">Added</th>
                    <th className="num" />
                  </tr>
                </thead>
                <tbody>
                  {filtered.length === 0 && (
                    <tr className="empty-row">
                      <td colSpan={7}>
                        No roles here yet. Track one from Live jobs, or import a listing to start the pipeline.
                      </td>
                    </tr>
                  )}
                  {filtered.map((job) => {
                    const isOpen = expanded === `job-${job.id}`;
                    const hasScore = Number(job.match_score) > 0;
                    return (
                      <JobRow
                        key={job.id}
                        job={job}
                        isOpen={isOpen}
                        busy={busy}
                        hasScore={hasScore}
                        copiedId={copiedId}
                        onToggle={() => setExpanded(isOpen ? "" : `job-${job.id}`)}
                        onStatus={(status) => updateStatus(job, status)}
                        onPrepare={() => prepare(job)}
                        onCopy={() => {
                          navigator.clipboard.writeText(job.cover_letter_draft || "");
                          setCopiedId(`cl-${job.id}`);
                          setTimeout(() => setCopiedId(""), 1800);
                        }}
                      />
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </>
  );
}

function JobRow({ job, isOpen, busy, hasScore, copiedId, onToggle, onStatus, onPrepare, onCopy }) {
  const hasPackage = Boolean(job.cv_edits_suggestion || job.cover_letter_draft);
  return (
    <>
      <tr className="job-row" onClick={onToggle}>
        <td>
          <div className="job-role">
            <span className="cell-main">{job.title}</span>
            <span className="cell-sub">{job.company || "Company not specified"}</span>
          </div>
        </td>
        <td>
          <span className="cell-main" style={{ fontSize: 12, fontWeight: 400 }}>
            {job.location || "—"}
          </span>
          <span className="cell-sub">{job.work_mode}</span>
        </td>
        <td>
          {hasScore ? (
            <div className="score">
              <span className="score-bar">
                <span
                  className={`score-fill ${scoreTone(job.match_score)}`}
                  style={{ width: `${Math.min(100, Number(job.match_score) || 0)}%` }}
                />
              </span>
              <span className="score-value">{job.match_score}%</span>
            </div>
          ) : (
            <span className="badge">Not assessed</span>
          )}
        </td>
        <td>
          <span
            className={`badge ${
              job.sponsorship === "yes" ? "ok" : job.sponsorship === "no" ? "err" : "neutral"
            }`}
          >
            {job.sponsorship}
          </span>
        </td>
        <td onClick={(event) => event.stopPropagation()}>
          <select
            className="select-sm"
            value={job.status}
            onChange={(event) => onStatus(event.target.value)}
            aria-label={`Status for ${job.title}`}
          >
            {STATUSES.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>
        </td>
        <td className="nowrap">{relativeTime(job.created_at)}</td>
        <td className="num">
          <button
            type="button"
            className="link-btn"
            onClick={(event) => {
              event.stopPropagation();
              onToggle();
            }}
          >
            {isOpen ? <ChevronUp /> : <ChevronDown />}
          </button>
        </td>
      </tr>
      {isOpen && (
        <tr className="job-expand">
          <td colSpan={7}>
            <div className="job-detail">
              <div className="detail-block">
                <div className="detail-title">CV evidence</div>
                {(job.match_reasons || []).length ? (
                  <ul className="detail-list">
                    {job.match_reasons.map((reason, index) => (
                      <li key={index}>{reason}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="detail-text">
                    Not assessed yet. Prepare an application to generate CV evidence and fit scoring.
                  </p>
                )}
              </div>

              <div className="detail-block">
                <div className="detail-title">Gaps &amp; constraints</div>
                <ul className="detail-list">
                  {(job.gaps || []).map((gap, index) => (
                    <li key={`gap-${index}`}>{gap}</li>
                  ))}
                  {(job.constraints || []).map((constraint, index) => (
                    <li key={`constraint-${index}`}>{constraint}</li>
                  ))}
                  {!(job.gaps || []).length && !(job.constraints || []).length && <li>None recorded.</li>}
                </ul>
              </div>

              {job.cv_edits_suggestion && (
                <div className="detail-block full">
                  <div className="detail-title">Suggested CV tailoring</div>
                  <pre className="detail-text">{job.cv_edits_suggestion}</pre>
                </div>
              )}

              {job.cover_letter_draft && (
                <div className="detail-block full">
                  <div className="detail-title" style={{ justifyContent: "space-between" }}>
                    <span>Cover letter draft</span>
                    <button type="button" className="link-btn" onClick={onCopy}>
                      {copiedId === `cl-${job.id}` ? <Check /> : <Copy />}
                      {copiedId === `cl-${job.id}` ? "Copied" : "Copy"}
                    </button>
                  </div>
                  <pre className="detail-text">{job.cover_letter_draft}</pre>
                </div>
              )}

              {(job.screening_qa || []).length > 0 && (
                <div className="detail-block full">
                  <div className="detail-title">Screening questions &amp; answers</div>
                  {job.screening_qa.map((qa, index) => (
                    <div className="qa-item" key={index}>
                      <div className="qa-q">Q: {qa.question}</div>
                      <div className="qa-a">A: {qa.answer}</div>
                    </div>
                  ))}
                </div>
              )}

              <div className="detail-actions">
                <button className="btn btn-dark btn-sm" type="button" disabled={busy} onClick={onPrepare}>
                  <Sparkles size={13} /> {hasPackage ? "Regenerate package" : "Prepare application"}
                </button>
                {job.apply_url && (
                  <a className="btn btn-sm" href={job.apply_url} target="_blank" rel="noreferrer">
                    <ExternalLink size={13} /> Open application link
                  </a>
                )}
                <span className="badge">{prettyStatus(job.status)}</span>
                {job.source_type && job.source_type !== "pasted" && (
                  <span className="badge">Source: {job.source_type}</span>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
