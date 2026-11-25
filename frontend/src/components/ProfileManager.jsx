import { useEffect, useState } from "react";
import {
  Check,
  CheckCircle2,
  Circle,
  Copy,
  ExternalLink,
  Link2,
  Plus,
  RefreshCw,
  Sparkles,
  Trash2,
  Upload,
  UserCheck,
  X,
} from "lucide-react";
import { api } from "../api";
import { initials } from "../utils";

const AUTO_FIELDS = [
  { key: "full_name", label: "Full name" },
  { key: "headline", label: "Headline" },
  { key: "about", label: "About" },
  { key: "skills", label: "Skills" },
  { key: "experience", label: "Experience" },
  { key: "target_roles", label: "Target roles" },
  { key: "preferred_locations", label: "Locations" },
  { key: "work_authorization", label: "Work authorization" },
  { key: "portfolio_links", label: "Links" },
  { key: "linkedin_raw_text", label: "LinkedIn profile text" },
];

const FIELD_LABELS = Object.fromEntries(AUTO_FIELDS.map((field) => [field.key, field.label]));

function splitLinks(links = []) {
  return {
    linkedin: links.find((url) => /linkedin\.com/i.test(url)) || "",
    github: links.find((url) => /github\.com/i.test(url)) || "",
    website: links.find((url) => !/linkedin\.com|github\.com/i.test(url)) || "",
  };
}

function FieldLabel({ children, field, autoFilled }) {
  return (
    <label className="field-label">
      {children}
      {autoFilled.includes(field) && (
        <span className="field-badge">
          <Sparkles /> AI filled
        </span>
      )}
    </label>
  );
}

export default function ProfileManager({ onChanged }) {
  const [profile, setProfile] = useState(null);
  const [notes, setNotes] = useState([]);
  const [review, setReview] = useState(null);
  const [linkedin, setLinkedin] = useState(null);
  const [identity, setIdentity] = useState(null);
  const [noteForm, setNoteForm] = useState({ title: "", content: "", github_url: "" });
  const [linkForm, setLinkForm] = useState({ linkedin: "", github: "", website: "" });
  const [linkedinText, setLinkedinText] = useState("");
  const [msg, setMsg] = useState("");
  const [syncNote, setSyncNote] = useState("");
  const [syncBusy, setSyncBusy] = useState(false);
  const [cvStage, setCvStage] = useState("");
  const [cvPercent, setCvPercent] = useState(0);
  const [autoFilled, setAutoFilled] = useState([]);
  const [busy, setBusy] = useState(false);
  const [aiReady, setAiReady] = useState(true);
  const [copiedKey, setCopiedKey] = useState("");

  const applyProfile = (next) => {
    setProfile(next);
    setLinkForm(splitLinks(next.portfolio_links || []));
  };

  const load = async () => {
    const [profileRes, notesRes, connectorsRes, settingsRes] = await Promise.allSettled([
      api.getProfile(),
      api.getNotes(),
      api.getConnectors(),
      api.getSettings(),
    ]);

    if (profileRes.status === "fulfilled") {
      applyProfile(profileRes.value);
    } else {
      setMsg(profileRes.reason?.message || "Could not load your profile. Is the backend running?");
    }
    if (notesRes.status === "fulfilled") setNotes(notesRes.value);
    if (connectorsRes.status === "fulfilled") {
      setLinkedin(connectorsRes.value.find((connector) => connector.platform === "linkedin") || null);
    }
    if (settingsRes.status === "fulfilled") {
      setAiReady(
        settingsRes.value.is_external
          ? Boolean(settingsRes.value.has_external_api_key)
          : Boolean(settingsRes.value.ollama_status?.running)
      );
    }
  };

  useEffect(() => {
    load();
  }, []);

  const copySection = (key, text) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(""), 1800);
  };

  const applyCvResult = (res, before) => {
    const changed = AUTO_FIELDS.filter(
      (field) => JSON.stringify(before?.[field.key]) !== JSON.stringify(res.profile?.[field.key])
    ).map((field) => field.key);
    applyProfile(res.profile);
    setAutoFilled(changed);
    if (res.warning) {
      setCvStage("");
      setMsg(res.warning);
    } else {
      setCvStage("done");
      setMsg(
        changed.length
          ? `CV parsed — ${changed.length} fields auto-filled. Review and confirm below.`
          : "CV parsed. Review the fields below."
      );
    }
    onChanged?.();
  };

  const handleCvUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const before = profile;
    setBusy(true);
    setAutoFilled([]);
    setCvPercent(0);
    setCvStage("uploading");
    setMsg("");
    try {
      const res = await api.uploadCvWithProgress(file, (percent) => {
        setCvPercent(percent);
        if (percent >= 100) setCvStage("extracting");
      });
      applyCvResult(res, before);
    } catch (err) {
      setCvStage("");
      setMsg(err.message);
    } finally {
      setBusy(false);
      event.target.value = "";
    }
  };

  const reextractSavedCv = async () => {
    const before = profile;
    setBusy(true);
    setAutoFilled([]);
    setCvPercent(100);
    setCvStage("extracting");
    setMsg("");
    try {
      const res = await api.reextractCv();
      applyCvResult(res, before);
    } catch (err) {
      setCvStage("");
      setMsg(err.message);
    } finally {
      setBusy(false);
    }
  };

  const runLinkedInSync = async (text) => {
    setSyncBusy(true);
    setSyncNote(text ? "Reading your profile text and extracting fields…" : "Fetching your verified LinkedIn identity…");
    setMsg("");
    try {
      const res = await api.importLinkedIn(text);
      const changed = res.updated_fields || [];
      applyProfile(res.profile);
      if (res.identity && Object.keys(res.identity).length) setIdentity(res.identity);
      setAutoFilled((prev) => [...new Set([...prev, ...changed])]);
      setLinkedinText("");
      setSyncNote("");
      setMsg(
        res.warning?.trim()
          ? res.warning
          : changed.length
          ? `${changed.length} fields synced from LinkedIn. Review and confirm below.`
          : "LinkedIn identity synced."
      );
      onChanged?.();
    } catch (err) {
      setSyncNote("");
      setMsg(err.message);
    } finally {
      setSyncBusy(false);
    }
  };

  const mergedLinks = () => {
    const known = [linkForm.linkedin, linkForm.github, linkForm.website]
      .map((value) => value.trim())
      .filter(Boolean);
    const extras = (profile.portfolio_links || [])
      .map((value) => String(value).trim())
      .filter(
        (value) =>
          value &&
          !/linkedin\.com/i.test(value) &&
          !/github\.com/i.test(value) &&
          value !== linkForm.website.trim()
      );
    const seen = new Set();
    return [...known, ...extras].filter((url) => {
      const key = url.replace(/^https?:\/\/(www\.)?/i, "").replace(/\/$/, "").toLowerCase();
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  };

  const saveProfile = async (confirmed) => {
    setBusy(true);
    try {
      const updated = await api.updateProfile({
        ...profile,
        portfolio_links: mergedLinks(),
        confirmed,
      });
      applyProfile(updated);
      setAutoFilled([]);
      setMsg(confirmed ? "Profile confirmed and active across every agent module." : "Draft saved.");
      onChanged?.();
    } catch (err) {
      setMsg(err.message);
    } finally {
      setBusy(false);
    }
  };

  const runReview = async () => {
    setBusy(true);
    setMsg("Reviewing your LinkedIn sections against your target roles…");
    try {
      const res = await api.reviewProfile();
      setReview(res.review);
      setMsg(`Profile review complete (${res.ai_provider_used}).`);
    } catch (err) {
      setMsg(err.message);
    } finally {
      setBusy(false);
    }
  };

  const addNote = async (event) => {
    event.preventDefault();
    if (!noteForm.title.trim() || !noteForm.content.trim()) return;
    await api.createNote({ ...noteForm, tags: [] });
    setNoteForm({ title: "", content: "", github_url: "" });
    load();
    onChanged?.();
  };

  const deleteNote = async (id) => {
    await api.deleteNote(id);
    load();
    onChanged?.();
  };

  const experience = profile?.experience || [];
  const updateExperience = (index, patch) => {
    setProfile({
      ...profile,
      experience: experience.map((item, itemIndex) =>
        itemIndex === index ? { ...item, ...patch } : item
      ),
    });
  };
  const removeExperience = (index) => {
    setProfile({ ...profile, experience: experience.filter((_, itemIndex) => itemIndex !== index) });
  };
  const addExperience = () => {
    setProfile({
      ...profile,
      experience: [...experience, { title: "", company: "", duration: "", highlights: [] }],
    });
  };

  if (!profile) return <p className="muted">Loading your profile…</p>;

  const completeness = [
    { label: "CV uploaded", done: Boolean(profile.cv_filename) },
    { label: "Headline", done: Boolean(profile.headline?.trim()) },
    { label: "About section", done: Boolean(profile.about?.trim()) },
    { label: "Skills", done: (profile.skills || []).length > 0 },
    { label: "Target roles", done: (profile.target_roles || []).length > 0 },
    { label: "Experience entries", done: experience.length > 0 },
    { label: "LinkedIn / portfolio links", done: Boolean(linkForm.linkedin || linkForm.website || linkForm.github) },
    { label: "Project notes", done: notes.length > 0 },
  ];
  const doneCount = completeness.filter((item) => item.done).length;
  const percent = Math.round((doneCount / completeness.length) * 100);

  const listValue = (items) => (items || []).join(", ");
  const splitList = (value) =>
    value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);

  const avatarPicture = identity?.picture || "";

  return (
    <>
      <div className="page-head">
        <div>
          <div className="page-eyebrow">
            <UserCheck size={12} /> Knowledge base
          </div>
          <h2 className="page-title">Profile, CV &amp; knowledge</h2>
          <p className="page-sub">
            Import from LinkedIn, upload your CV and review every auto-filled field. All drafts and
            applications are grounded in this verified baseline.
          </p>
        </div>
        <div className="head-actions">
          {linkForm.linkedin && (
            <a className="btn" href={linkForm.linkedin} target="_blank" rel="noreferrer">
              <ExternalLink size={14} /> View LinkedIn
            </a>
          )}
          <span className={`badge ${profile.confirmed ? "ok" : "warn"}`}>
            <span className="dot" /> {profile.confirmed ? "Profile confirmed" : "Pending confirmation"}
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

      {autoFilled.length > 0 && (
        <div className="auto-summary" style={{ marginBottom: 12 }}>
          <CheckCircle2 />
          <span>
            Auto-filled {autoFilled.length} {autoFilled.length === 1 ? "field" : "fields"}:{" "}
            {autoFilled.map((field) => FIELD_LABELS[field] || field).join(", ")}. Check the highlighted
            fields, then confirm your profile.
          </span>
        </div>
      )}

      <section className="card" style={{ marginBottom: 12 }}>
        <div className="card-hd">
          <div>
            <h3 className="card-title">
              <RefreshCw size={15} /> LinkedIn profile sync
            </h3>
            <p className="card-desc">
              Pull your verified identity from the connected account, then complete the sections LinkedIn
              does not expose to apps.
            </p>
          </div>
          <span className={`badge ${linkedin?.connected ? "ok" : "warn"}`}>
            <span className="dot" />
            {linkedin?.connected ? `Connected · ${linkedin.account_label || "LinkedIn"}` : "Not connected"}
          </span>
        </div>

        <div className="sync-grid">
          <div className="sync-block">
            <div className="identity-strip">
              {avatarPicture ? (
                <img className="identity-avatar" src={avatarPicture} alt="LinkedIn profile" />
              ) : (
                <span className="identity-avatar fallback">{initials(identity?.name || profile.full_name)}</span>
              )}
              <div style={{ minWidth: 0 }}>
                <div className="identity-name">{identity?.name || profile.full_name || "LinkedIn account"}</div>
                <div className="identity-sub">
                  {identity?.email || linkedin?.account_label || "Connect LinkedIn to fetch your identity"}
                </div>
              </div>
            </div>

            <p className="sync-hint">
              LinkedIn&apos;s official API shares only your verified name, photo and email. Headline, About,
              skills and experience are private — paste your profile text and the agent will extract them.
            </p>

            <div className="sync-actions">
              <button
                className="btn btn-dark btn-sm"
                type="button"
                disabled={syncBusy || !linkedin?.connected}
                onClick={() => runLinkedInSync("")}
              >
                {syncBusy ? <span className="spinner light" /> : <RefreshCw size={13} />} Fetch identity
              </button>
              {linkForm.linkedin && (
                <a className="btn btn-sm" href={linkForm.linkedin} target="_blank" rel="noreferrer">
                  <ExternalLink size={13} /> Open profile
                </a>
              )}
            </div>
            {syncNote && (
              <div className="upload-status">
                <span className="spinner" /> {syncNote}
              </div>
            )}
          </div>

          <div className="sync-block">
            <label className="field-label">
              <Link2 size={12} /> Paste LinkedIn profile text
            </label>
            <textarea
              className="linkedin-textarea"
              value={linkedinText}
              onChange={(event) => setLinkedinText(event.target.value)}
              placeholder="Open your LinkedIn profile, select all (Ctrl+A), copy and paste here. The agent extracts headline, About, skills, experience, locations and links."
            />
            <div className="row" style={{ justifyContent: "space-between", marginTop: 8 }}>
              <span className="field-hint" style={{ margin: 0 }}>
                Grounded extraction — no invented facts.
              </span>
              <button
                className="btn btn-sm"
                type="button"
                disabled={syncBusy || !linkedinText.trim()}
                onClick={() => runLinkedInSync(linkedinText)}
              >
                {syncBusy ? <span className="spinner" /> : <Sparkles size={13} />} Sync full profile
              </button>
            </div>
          </div>
        </div>
      </section>

      <div className="profile-grid">
        <section className="card">
          <div className="card-hd">
            <div className="row" style={{ gap: 10, flexWrap: "nowrap" }}>
              <span className="profile-avatar">
                {avatarPicture ? <img src={avatarPicture} alt="" /> : initials(profile.full_name)}
              </span>
              <div>
                <h3 className="card-title">
                  <Upload size={15} /> Editable profile
                </h3>
                <p className="card-desc">Upload a CV to auto-fill, then correct anything that looks off.</p>
              </div>
            </div>
            <span className={`badge ${profile.confirmed ? "ok" : "warn"}`}>
              {profile.confirmed ? "Verified" : "Draft"}
            </span>
          </div>

          <div className="upload-zone" style={{ marginBottom: 14 }}>
            <div className="upload-zone-title">
              <Upload /> CV upload &amp; auto-fill
            </div>
            <div className="upload-row">
              <label className={`btn btn-sm file-btn ${busy ? "disabled" : ""}`}>
                <Upload size={13} /> Choose CV
                <input
                  type="file"
                  className="hidden-input"
                  accept=".pdf,.docx,.txt,.md"
                  onChange={handleCvUpload}
                  disabled={busy}
                />
              </label>
              {profile.cv_filename && (
                <button className="btn btn-sm" type="button" onClick={reextractSavedCv} disabled={busy}>
                  {cvStage === "extracting" ? <span className="spinner" /> : <Sparkles size={13} />} Re-extract saved CV
                </button>
              )}
              <span className="field-hint" style={{ margin: 0 }}>
                {profile.cv_filename ? (
                  <>
                    Loaded: <strong style={{ color: "var(--steel)" }}>{profile.cv_filename}</strong>
                  </>
                ) : (
                  "PDF, DOCX, TXT or MD"
                )}
              </span>
            </div>

            {!aiReady && (
              <p className="field-hint" style={{ marginTop: 8, color: "#b45309" }}>
                The AI engine is offline. Your file is saved, but start Ollama (or switch provider in AI
                &amp; Privacy) to auto-fill fields.
              </p>
            )}

            {cvStage && (
              <div className="upload-progress">
                <div className="upload-progress-hd">
                  <span>
                    {cvStage === "uploading"
                      ? `Uploading ${cvPercent}%`
                      : cvStage === "extracting"
                      ? "Reading your CV and extracting fields…"
                      : "CV processed"}
                  </span>
                  <span>{cvStage === "uploading" ? `${cvPercent}%` : cvStage === "done" ? "Done" : ""}</span>
                </div>
                <div className={`progress-track ${cvStage === "extracting" ? "indeterminate" : ""}`}>
                  <span
                    className="progress-fill"
                    style={{ width: cvStage === "uploading" ? `${cvPercent}%` : "100%" }}
                  />
                </div>
                <div className="upload-status">
                  {cvStage !== "done" && <span className="spinner" />}
                  {cvStage === "extracting"
                    ? "The local model is mapping your experience, skills and links."
                    : cvStage === "done"
                    ? "Fields below were updated from your CV."
                    : "Sending your file securely to the local backend."}
                </div>
              </div>
            )}
          </div>

          <div className="form-section">
            <h4 className="form-section-title">Identity</h4>
            <div className="field-grid">
              <div className="field">
                <FieldLabel field="full_name" autoFilled={autoFilled}>
                  Full name
                </FieldLabel>
                <input
                  value={profile.full_name || ""}
                  onChange={(event) => setProfile({ ...profile, full_name: event.target.value })}
                />
              </div>
              <div className="field">
                <FieldLabel field="work_authorization" autoFilled={autoFilled}>
                  Work authorization
                </FieldLabel>
                <input
                  value={profile.work_authorization || ""}
                  onChange={(event) => setProfile({ ...profile, work_authorization: event.target.value })}
                  placeholder="Optional"
                />
              </div>
              <div className="field span-2">
                <FieldLabel field="headline" autoFilled={autoFilled}>
                  LinkedIn headline
                </FieldLabel>
                <input
                  value={profile.headline || ""}
                  onChange={(event) => setProfile({ ...profile, headline: event.target.value })}
                  placeholder="AI/ML Engineer · Computer Vision · Generative AI"
                />
              </div>
              <div className="field span-2">
                <FieldLabel field="about" autoFilled={autoFilled}>
                  About section
                </FieldLabel>
                <textarea
                  value={profile.about || ""}
                  onChange={(event) => setProfile({ ...profile, about: event.target.value })}
                />
              </div>
            </div>
          </div>

          <div className="form-section">
            <h4 className="form-section-title">Positioning</h4>
            <div className="field">
              <FieldLabel field="skills" autoFilled={autoFilled}>
                Skills (comma-separated)
              </FieldLabel>
              <input
                value={listValue(profile.skills)}
                onChange={(event) => setProfile({ ...profile, skills: splitList(event.target.value) })}
              />
            </div>
            <div className="field">
              <FieldLabel field="target_roles" autoFilled={autoFilled}>
                Target roles (comma-separated)
              </FieldLabel>
              <input
                value={listValue(profile.target_roles)}
                onChange={(event) => setProfile({ ...profile, target_roles: splitList(event.target.value) })}
              />
            </div>
            <div className="field">
              <FieldLabel field="preferred_locations" autoFilled={autoFilled}>
                Preferred locations (comma-separated)
              </FieldLabel>
              <input
                value={listValue(profile.preferred_locations)}
                onChange={(event) =>
                  setProfile({ ...profile, preferred_locations: splitList(event.target.value) })
                }
              />
            </div>
            <div className="field-grid">
              <div className="field">
                <label className="field-label">Work preferences</label>
                <input
                  value={profile.work_preferences || ""}
                  onChange={(event) => setProfile({ ...profile, work_preferences: event.target.value })}
                  placeholder="Remote / Hybrid / Onsite"
                />
              </div>
              <div className="field">
                <label className="field-label">Writing voice</label>
                <input
                  value={profile.voice_notes || ""}
                  onChange={(event) => setProfile({ ...profile, voice_notes: event.target.value })}
                  placeholder="Technical, concise, metrics-focused"
                />
              </div>
            </div>
          </div>

          <div className="form-section">
            <h4 className="form-section-title">
              <Link2 size={11} style={{ verticalAlign: "-1px", marginRight: 4 }} /> Relevant URLs
            </h4>
            <div className="field">
              <FieldLabel field="portfolio_links" autoFilled={autoFilled}>
                LinkedIn profile URL
              </FieldLabel>
              <div style={{ display: "flex", gap: 6 }}>
                <input
                  value={linkForm.linkedin}
                  onChange={(event) => setLinkForm({ ...linkForm, linkedin: event.target.value })}
                  placeholder="https://www.linkedin.com/in/your-handle"
                />
                {linkForm.linkedin && (
                  <a className="btn btn-sm" href={linkForm.linkedin} target="_blank" rel="noreferrer">
                    <ExternalLink size={13} />
                  </a>
                )}
              </div>
            </div>
            <div className="field-grid">
              <div className="field">
                <label className="field-label">GitHub</label>
                <input
                  value={linkForm.github}
                  onChange={(event) => setLinkForm({ ...linkForm, github: event.target.value })}
                  placeholder="https://github.com/your-handle"
                />
              </div>
              <div className="field">
                <label className="field-label">Portfolio / website</label>
                <input
                  value={linkForm.website}
                  onChange={(event) => setLinkForm({ ...linkForm, website: event.target.value })}
                  placeholder="https://your-site.com"
                />
              </div>
            </div>
          </div>

          <div className="form-section">
            <h4 className="form-section-title">Experience</h4>
            {experience.length === 0 && (
              <p className="field-hint" style={{ marginTop: 0 }}>
                No experience entries yet. Upload a CV or add one manually.
              </p>
            )}
            {experience.map((item, index) => (
              <div className="experience-item" key={index}>
                <div className="experience-hd">
                  <span className="experience-title">Role {index + 1}</span>
                  <button
                    className="icon-btn"
                    type="button"
                    onClick={() => removeExperience(index)}
                    title="Remove experience"
                  >
                    <Trash2 />
                  </button>
                </div>
                <div className="field-grid">
                  <div className="field">
                    <label className="field-label">Title</label>
                    <input
                      value={item.title || ""}
                      onChange={(event) => updateExperience(index, { title: event.target.value })}
                    />
                  </div>
                  <div className="field">
                    <label className="field-label">Company</label>
                    <input
                      value={item.company || ""}
                      onChange={(event) => updateExperience(index, { company: event.target.value })}
                    />
                  </div>
                  <div className="field">
                    <label className="field-label">Duration</label>
                    <input
                      value={item.duration || ""}
                      onChange={(event) => updateExperience(index, { duration: event.target.value })}
                      placeholder="2023 — Present"
                    />
                  </div>
                  <div className="field">
                    <label className="field-label">Highlights (one per line)</label>
                    <textarea
                      style={{ minHeight: 64 }}
                      value={(item.highlights || []).join("\n")}
                      onChange={(event) =>
                        updateExperience(index, {
                          highlights: event.target.value.split("\n").map((line) => line.trim()).filter(Boolean),
                        })
                      }
                    />
                  </div>
                </div>
              </div>
            ))}
            <button className="btn btn-sm experience-add" type="button" onClick={addExperience}>
              <Plus size={13} /> Add experience
            </button>
          </div>

          <div className="form-actions">
            <button className="btn btn-dark" type="button" onClick={() => saveProfile(true)} disabled={busy}>
              <Check size={14} /> {profile.confirmed ? "Update confirmed profile" : "Confirm profile"}
            </button>
            <button className="btn" type="button" onClick={() => saveProfile(false)} disabled={busy}>
              Save draft
            </button>
            <button className="btn" type="button" onClick={runReview} disabled={busy}>
              <Sparkles size={14} /> Review LinkedIn profile
            </button>
          </div>
        </section>

        <div className="stack">
          <section className="card">
            <div className="card-hd">
              <div>
                <h3 className="card-title">
                  <UserCheck size={15} /> Profile strength
                </h3>
                <p className="card-desc">Complete fields improve every grounded draft.</p>
              </div>
              <span className="badge">{percent}%</span>
            </div>
            <div className="bar" style={{ marginBottom: 12 }}>
              <span className="bar-fill" style={{ width: `${percent}%` }} />
            </div>
            <div className="checklist">
              {completeness.map((item) => (
                <div className={`check-row ${item.done ? "done" : ""}`} key={item.label}>
                  {item.done ? <Check /> : <Circle />}
                  {item.label}
                </div>
              ))}
            </div>
          </section>

          <section className="card">
            <div className="card-hd">
              <div>
                <h3 className="card-title">
                  <Sparkles size={15} /> Project notes
                </h3>
                <p className="card-desc">Raw material for posts and applications.</p>
              </div>
              <span className="badge">{notes.length}</span>
            </div>

            <form onSubmit={addNote}>
              <div className="field">
                <label className="field-label">Project title</label>
                <input
                  value={noteForm.title}
                  onChange={(event) => setNoteForm({ ...noteForm, title: event.target.value })}
                  placeholder="e.g. QuantEye"
                />
              </div>
              <div className="field">
                <label className="field-label">GitHub / portfolio link</label>
                <input
                  value={noteForm.github_url}
                  onChange={(event) => setNoteForm({ ...noteForm, github_url: event.target.value })}
                  placeholder="https://github.com/…"
                />
              </div>
              <div className="field">
                <label className="field-label">Technical notes &amp; outcomes</label>
                <textarea
                  value={noteForm.content}
                  onChange={(event) => setNoteForm({ ...noteForm, content: event.target.value })}
                  placeholder="Architecture, model choices, benchmarks, real results…"
                />
              </div>
              <button className="btn btn-block" type="submit">
                Add project note
              </button>
            </form>

            {notes.length > 0 && (
              <div style={{ marginTop: 14 }}>
                {notes.map((note) => (
                  <div className="note-item" key={note.id}>
                    <div className="note-hd">
                      <div>
                        <div className="note-title">{note.title}</div>
                        {note.github_url && <span className="note-link">{note.github_url}</span>}
                      </div>
                      <button className="icon-btn" type="button" onClick={() => deleteNote(note.id)} title="Delete note">
                        <Trash2 />
                      </button>
                    </div>
                    <p className="note-body">{note.content}</p>
                  </div>
                ))}
              </div>
            )}
          </section>

          {review && (
            <section className="card">
              <div className="card-hd">
                <div>
                  <h3 className="card-title">
                    <Sparkles size={15} /> LinkedIn review
                  </h3>
                  <p className="card-desc">Proposed rewrites grounded in your evidence.</p>
                </div>
              </div>
              {["headline", "about", "skills", "experience"].map((section) => {
                const item = review[section];
                if (!item) return null;
                const proposedText =
                  typeof item.proposed === "string" ? item.proposed : JSON.stringify(item.proposed, null, 2);
                return (
                  <div className="review-item" key={section}>
                    <div className="review-hd">
                      <span className="review-label">{section}</span>
                      <button className="btn btn-sm" type="button" onClick={() => copySection(section, proposedText)}>
                        {copiedKey === section ? <Check size={13} /> : <Copy size={13} />}
                        {copiedKey === section ? "Copied" : "Copy"}
                      </button>
                    </div>
                    <div className="review-current">
                      Current: {typeof item.current === "string" ? item.current : JSON.stringify(item.current)}
                    </div>
                    <div className="review-proposed">{proposedText}</div>
                    {item.why_it_helps && <div className="review-why">Why it helps: {item.why_it_helps}</div>}
                  </div>
                );
              })}
            </section>
          )}
        </div>
      </div>
    </>
  );
}
