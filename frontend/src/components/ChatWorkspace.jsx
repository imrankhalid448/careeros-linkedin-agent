import { useEffect, useRef, useState } from "react";
import {
  Check,
  Copy,
  ExternalLink,
  Image as ImageIcon,
  MessageSquare,
  PenTool,
  Send,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  X,
} from "lucide-react";
import { api } from "../api";
import { initials } from "../utils";

const QUICK_PROMPTS = [
  {
    label: "Draft a post from my latest project",
    prompt:
      "Use my latest project note to draft a LinkedIn post in an authentic engineering voice, then show me the three roles that best match my CV.",
  },
  {
    label: "Review today's job matches",
    prompt: "Review my job pipeline and show me the three roles that best match my CV with reasons.",
  },
  {
    label: "Turn my project into a story",
    prompt:
      "Draft a concise LinkedIn post from my project notes focusing on the problem, approach, benchmark and takeaway.",
  },
];

const CAPABILITIES = [
  {
    icon: PenTool,
    title: "Draft LinkedIn posts",
    desc: "Grounded in your CV and project notes.",
  },
  {
    icon: MessageSquare,
    title: "Write thoughtful replies",
    desc: "Specific comments on posts you paste.",
  },
  {
    icon: Target,
    title: "Assess job fit",
    desc: "Scores roles against verified evidence.",
  },
  {
    icon: TrendingUp,
    title: "Prepare applications",
    desc: "CV edits, cover letters and screening answers.",
  },
];

export default function ChatWorkspace({ onOpenJobs, onChanged }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState("");
  const [editingPosts, setEditingPosts] = useState({});
  const [copiedId, setCopiedId] = useState(null);
  const [busyCard, setBusyCard] = useState("");
  const bodyRef = useRef(null);

  useEffect(() => {
    api.getChatHistory().then(setMessages).catch(() => {});
  }, []);

  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const sendMessage = async (textToSend) => {
    const text = (textToSend ?? input).trim();
    if (!text || loading) return;
    setInput("");
    setLoading(true);
    setStatusMsg("");
    try {
      const reply = await api.sendChat(text);
      setMessages((prev) => [
        ...prev,
        { id: `local-${Date.now()}`, role: "user", message: text, cards: [] },
        reply,
      ]);
      onChanged?.();
    } catch (err) {
      setStatusMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  const applyCardUpdate = (post, type = "post_draft") => {
    setMessages((prev) =>
      prev.map((message) => ({
        ...message,
        cards: (message.cards || []).map((card) =>
          card.type === type && card.data.id === post.id ? { ...card, data: post } : card
        ),
      }))
    );
  };

  const approveAndPublish = async (post) => {
    const updatedText = editingPosts[post.id] ?? post.content;
    setStatusMsg("");
    setBusyCard(`publish-${post.id}`);
    try {
      if (updatedText !== post.content) {
        await api.updatePost(post.id, { content: updatedText });
      }
      const res = await api.publishPost(post.id);
      setStatusMsg(res.message);
      applyCardUpdate(res.post);
      onChanged?.();
    } catch (err) {
      setStatusMsg(err.message);
    } finally {
      setBusyCard("");
    }
  };

  const generateImage = async (post) => {
    setStatusMsg("Generating a visual for this post...");
    setBusyCard(`image-${post.id}`);
    try {
      const res = await api.generatePostImage(post.id);
      setStatusMsg(`Image generated (${res.image_provider}).`);
      applyCardUpdate(res.post);
    } catch (err) {
      setStatusMsg(err.message);
    } finally {
      setBusyCard("");
    }
  };

  const prepareJobFromChat = async (jobId) => {
    setStatusMsg("Generating tailored CV edits, cover letter and screening answers...");
    setBusyCard(`job-${jobId}`);
    try {
      await api.prepareJob(jobId);
      setStatusMsg("Application package ready — opening the job pipeline.");
      onChanged?.();
      onOpenJobs?.();
    } catch (err) {
      setStatusMsg(err.message);
    } finally {
      setBusyCard("");
    }
  };

  const copyText = (id, text) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1800);
  };

  return (
    <>
      <div className="page-head">
        <div>
          <div className="page-eyebrow">
            <Sparkles size={12} /> Agent workspace
          </div>
          <h2 className="page-title">Command center</h2>
          <p className="page-sub">
            Give one multi-step instruction across your CV, project notes, posts and job pipeline. The agent
            prepares drafts; you approve what goes live.
          </p>
        </div>
        <div className="head-actions">
          <span className="status-pill">
            <span className="dot" style={{ background: "var(--green)" }} />
            Grounded in verified profile
          </span>
        </div>
      </div>

      {statusMsg && (
        <div className="banner">
          <span>{statusMsg}</span>
          <button type="button" className="banner-close" onClick={() => setStatusMsg("")} aria-label="Dismiss">
            <X size={14} />
          </button>
        </div>
      )}

      <div className="chat-grid">
        <section className="card chat-panel">
          <div className="chat-hd">
            <span className="avatar">
              <Sparkles size={15} />
            </span>
            <div>
              <div className="chat-hd-title">CareerOS agent</div>
              <div className="chat-hd-sub">LinkedIn drafting · job assessment · application prep</div>
            </div>
            <span className="badge ok" style={{ marginLeft: "auto" }}>
              <span className="dot" /> Ready
            </span>
          </div>

          <div className="chat-body" ref={bodyRef}>
            {messages.length === 0 && (
              <div className="chat-empty">
                <div className="chat-empty-mark">
                  <Sparkles size={19} />
                </div>
                <h4>Your agent is ready</h4>
                <p>
                  Ask it to draft a post from a project note, review job matches, or prepare a tailored
                  application. Upload your CV under Profile &amp; CV first for grounded results.
                </p>
                <div className="quick-grid" style={{ marginTop: 16, textAlign: "left" }}>
                  {QUICK_PROMPTS.map((item) => (
                    <button
                      type="button"
                      className="quick-card"
                      key={item.label}
                      onClick={() => setInput(item.prompt)}
                    >
                      <strong>{item.label}</strong>
                      <span>Fills the prompt box</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((message) => (
              <div className={`msg ${message.role === "user" ? "user" : ""}`} key={message.id}>
                <div className="msg-head">
                  {message.role === "user" ? (
                    <span className="msg-avatar">{initials("You")}</span>
                  ) : (
                    <span className="msg-avatar bot">
                      <Sparkles size={12} />
                    </span>
                  )}
                  <span className="msg-author">{message.role === "user" ? "You" : "CareerOS agent"}</span>
                  {message.ai_provider_used && <span className="badge">{message.ai_provider_used}</span>}
                </div>

                <pre className="msg-text">{message.message}</pre>

                {(message.cards || []).length > 0 && (
                  <div className="msg-cards">
                    {(message.cards || []).map((card, index) => {
                      if (card.type === "post_draft") {
                        const post = card.data;
                        const value = editingPosts[post.id] ?? post.content;
                        const published = post.status === "published";
                        return (
                          <div className="draft-card" key={`post-${index}`}>
                            <div className="draft-hd">
                              <div>
                                <div className="draft-title">{post.title}</div>
                                <div className="draft-meta">
                                  <span className={`badge ${published ? "ok" : "warn"}`}>
                                    {published ? "Published" : "Needs approval"}
                                  </span>
                                  <span className="badge">LinkedIn</span>
                                </div>
                              </div>
                              <span className="char-count">{value.length} / 3000</span>
                            </div>

                            <textarea
                              value={value}
                              disabled={published}
                              onChange={(event) =>
                                setEditingPosts({ ...editingPosts, [post.id]: event.target.value })
                              }
                            />

                            {post.image_path && (
                              <img
                                src={`/api/media/${post.image_path}`}
                                alt="Generated post visual"
                                className="img-preview"
                              />
                            )}

                            {post.error_message && <p className="note-error">{post.error_message}</p>}

                            <div className="draft-actions">
                              <div className="row" style={{ gap: 6 }}>
                                <button
                                  type="button"
                                  className="btn btn-dark btn-sm"
                                  disabled={published || busyCard === `publish-${post.id}`}
                                  onClick={() => approveAndPublish(post)}
                                >
                                  <Send size={13} /> {published ? "Published" : "Approve & publish"}
                                </button>
                                {!published && (
                                  <button
                                    type="button"
                                    className="btn btn-sm"
                                    disabled={busyCard === `image-${post.id}`}
                                    onClick={() => generateImage(post)}
                                  >
                                    <ImageIcon size={13} /> Visual
                                  </button>
                                )}
                                <button
                                  type="button"
                                  className="btn btn-sm"
                                  onClick={() => copyText(`post-${post.id}`, value)}
                                >
                                  {copiedId === `post-${post.id}` ? <Check size={13} /> : <Copy size={13} />}
                                  {copiedId === `post-${post.id}` ? "Copied" : "Copy"}
                                </button>
                              </div>
                              {post.external_post_url && (
                                <a
                                  className="link-btn"
                                  href={post.external_post_url}
                                  target="_blank"
                                  rel="noreferrer"
                                >
                                  View post <ExternalLink />
                                </a>
                              )}
                            </div>
                          </div>
                        );
                      }

                      if (card.type === "job_match") {
                        const job = card.data;
                        return (
                          <div className="draft-card" key={`job-${index}`}>
                            <div className="draft-hd">
                              <div>
                                <div className="draft-title">
                                  {job.title}
                                  {job.company ? ` — ${job.company}` : ""}
                                </div>
                                <div className="draft-meta">
                                  <span className="badge">{job.location || "Location unspecified"}</span>
                                  <span className="badge">{job.work_mode}</span>
                                  <span className="badge warn">Sponsorship: {job.sponsorship}</span>
                                </div>
                              </div>
                              <span className="badge ok">Match {job.match_score}%</span>
                            </div>

                            {(job.match_reasons || []).length > 0 && (
                              <ul className="match-list">
                                {(job.match_reasons || []).slice(0, 3).map((reason, reasonIndex) => (
                                  <li key={reasonIndex}>{reason}</li>
                                ))}
                              </ul>
                            )}

                            <div className="draft-actions">
                              <button
                                type="button"
                                className="btn btn-sm"
                                disabled={busyCard === `job-${job.id}`}
                                onClick={() => prepareJobFromChat(job.id)}
                              >
                                <Sparkles size={13} /> Prepare application
                              </button>
                              {job.apply_url && (
                                <a
                                  className="btn btn-sm"
                                  href={job.apply_url}
                                  target="_blank"
                                  rel="noreferrer"
                                >
                                  <ExternalLink size={13} /> Apply link
                                </a>
                              )}
                            </div>
                          </div>
                        );
                      }

                      return null;
                    })}
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="msg">
                <div className="msg-head">
                  <span className="msg-avatar bot">
                    <Sparkles size={12} />
                  </span>
                  <span className="msg-author">CareerOS agent</span>
                  <span className="msg-time">working…</span>
                </div>
                <pre className="msg-text">Reading your workspace and drafting a grounded response…</pre>
              </div>
            )}
          </div>

          <form
            className="composer"
            onSubmit={(event) => {
              event.preventDefault();
              sendMessage();
            }}
          >
            <div className="composer-inner">
              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    sendMessage();
                  }
                }}
                placeholder="Ask your agent to draft a post, assess jobs, or prepare an application…"
                rows={2}
              />
              <div className="composer-actions">
                <span className="composer-hint">
                  <ShieldCheck size={12} /> Nothing publishes without approval
                </span>
                <button type="submit" className="btn btn-dark btn-sm" disabled={loading || !input.trim()}>
                  <Send size={13} /> {loading ? "Working…" : "Run command"}
                </button>
              </div>
            </div>
          </form>
        </section>

        <aside className="chat-rail">
          <div className="rail-card">
            <h4>Quick commands</h4>
            {QUICK_PROMPTS.map((item) => (
              <button
                type="button"
                className="quick-item"
                key={item.label}
                onClick={() => setInput(item.prompt)}
              >
                <Sparkles />
                {item.label}
              </button>
            ))}
          </div>

          <div className="rail-card">
            <h4>Agent capabilities</h4>
            {CAPABILITIES.map((capability) => {
              const Icon = capability.icon;
              return (
                <div className="cap-item" key={capability.title}>
                  <span className="cap-icon">
                    <Icon />
                  </span>
                  <div>
                    <div className="cap-title">{capability.title}</div>
                    <div className="cap-desc">{capability.desc}</div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="safety-note">
            <ShieldCheck />
            <span>
              The agent never invents experience. Every draft is grounded in your CV, project notes and
              confirmed profile, and requires your approval before publishing.
            </span>
          </div>
        </aside>
      </div>
    </>
  );
}
