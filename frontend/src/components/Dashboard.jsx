import { useMemo } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Briefcase,
  CheckCircle2,
  Circle,
  Clock,
  ExternalLink,
  MessageSquare,
  PenTool,
  Sparkles,
  Target,
  Zap,
} from "lucide-react";
import {
  firstName,
  localDayKey,
  prettyStatus,
  relativeTime,
  scoreTone,
  statusTone,
} from "../utils";

const PIPELINE = [
  { name: "Saved", color: "#c8c8c8" },
  { name: "Preparing", color: "#7c3aed" },
  { name: "Applied", color: "#2563eb" },
  { name: "Interview", color: "#ea580c" },
  { name: "Offer", color: "#16a34a" },
  { name: "Rejected", color: "#ef4444" },
];

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export default function Dashboard({
  profile,
  posts = [],
  comments = [],
  jobs = [],
  notes = [],
  settings,
  linkedin,
  onNavigate,
}) {
  const stats = useMemo(() => {
    const publishedPosts = posts.filter((post) => post.status === "published").length;
    const draftPosts = posts.filter((post) => post.status === "draft").length;
    const scheduledPosts = posts.filter((post) => post.status === "scheduled").length;
    const publishedComments = comments.filter((comment) => comment.status === "published").length;
    const draftComments = comments.filter((comment) =>
      ["draft", "manual_required"].includes(comment.status)
    ).length;
    const applications = jobs.filter((job) =>
      ["Applied", "Interview", "Offer"].includes(job.status)
    ).length;
    const preparing = jobs.filter((job) => job.status === "Preparing").length;
    const interviews = jobs.filter((job) => job.status === "Interview").length;
    const scored = jobs.filter((job) => Number(job.match_score) > 0);
    const avgFit = scored.length
      ? Math.round(scored.reduce((sum, job) => sum + Number(job.match_score), 0) / scored.length)
      : 0;

    return {
      publishedPosts,
      draftPosts,
      scheduledPosts,
      publishedComments,
      draftComments,
      applications,
      preparing,
      interviews,
      avgFit,
    };
  }, [posts, comments, jobs]);

  const days = useMemo(() => {
    const output = [];
    for (let i = 6; i >= 0; i -= 1) {
      const date = new Date();
      date.setDate(date.getDate() - i);
      const key = localDayKey(date);
      output.push({
        key,
        label: date.toLocaleDateString(undefined, { weekday: "short" }).slice(0, 2),
        count: 0,
      });
    }
    const byKey = Object.fromEntries(output.map((day) => [day.key, day]));
    const track = (items) => {
      items.forEach((item) => {
        const key = localDayKey(item.created_at);
        if (byKey[key]) byKey[key].count += 1;
      });
    };
    track(posts);
    track(comments);
    track(jobs);
    return output;
  }, [posts, comments, jobs]);

  const maxDay = Math.max(1, ...days.map((day) => day.count));
  const weekTotal = days.reduce((sum, day) => sum + day.count, 0);

  const pipelineMax = Math.max(1, ...PIPELINE.map((stage) => jobs.filter((job) => job.status === stage.name).length));

  const queue = useMemo(() => {
    const items = [
      ...posts
        .filter((post) => ["draft", "scheduled"].includes(post.status))
        .map((post) => ({
          key: `post-${post.id}`,
          kind: "Post",
          title: post.title || "Untitled post",
          sub: post.content,
          status: post.status,
          created_at: post.created_at,
          tone: "info",
        })),
      ...comments
        .filter((comment) => ["draft", "manual_required"].includes(comment.status))
        .map((comment) => ({
          key: `comment-${comment.id}`,
          kind: "Comment",
          title: "LinkedIn reply draft",
          sub: comment.draft_reply,
          status: comment.status,
          created_at: comment.created_at,
          tone: "violet",
        })),
    ];
    return items
      .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")))
      .slice(0, 6);
  }, [posts, comments]);

  const feed = useMemo(() => {
    const items = [
      ...posts.map((post) => ({
        key: `feed-post-${post.id}`,
        text: post.title || "LinkedIn post",
        status: post.status,
        created_at: post.created_at,
      })),
      ...comments.map((comment) => ({
        key: `feed-comment-${comment.id}`,
        text: "Reply draft",
        status: comment.status,
        created_at: comment.created_at,
      })),
      ...jobs.map((job) => ({
        key: `feed-job-${job.id}`,
        text: `${job.title}${job.company ? ` · ${job.company}` : ""}`,
        status: job.status,
        created_at: job.created_at,
      })),
    ];
    return items
      .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")))
      .slice(0, 4);
  }, [posts, comments, jobs]);

  const topJobs = useMemo(
    () => [...jobs].sort((a, b) => Number(b.match_score) - Number(a.match_score)).slice(0, 5),
    [jobs]
  );

  const aiReady = settings?.is_external
    ? Boolean(settings?.has_external_api_key)
    : Boolean(settings?.ollama_status?.running);

  const readiness = [
    { label: "CV uploaded", done: Boolean(profile?.cv_filename), hint: profile?.cv_filename ? "Parsed" : "Required" },
    { label: "Profile confirmed", done: Boolean(profile?.confirmed), hint: profile?.confirmed ? "Verified" : "Pending" },
    { label: "LinkedIn connected", done: Boolean(linkedin?.connected), hint: linkedin?.connected ? "Live" : "Connect" },
    { label: "Project knowledge", done: notes.length > 0, hint: `${notes.length} notes` },
    { label: "Agent engine", done: aiReady, hint: settings?.is_external ? "External" : "Ollama" },
  ];
  const readyCount = readiness.filter((item) => item.done).length;
  const readyPercent = Math.round((readyCount / readiness.length) * 100);

  return (
    <>
      <div className="page-head">
        <div>
          <div className="page-eyebrow">
            <span className="dot" style={{ background: "var(--green)" }} />
            Workspace overview
          </div>
          <h1 className="page-title">
            {greeting()}, {firstName(profile?.full_name)}
          </h1>
          <p className="page-sub">
            Your agent drafts posts, replies and tailored applications. Everything below is ready for your
            review and approval.
          </p>
        </div>
        <div className="head-actions">
          <button type="button" className="btn" onClick={() => onNavigate("content")}>
            Review queue
            {queue.length > 0 && <span className="badge">{queue.length}</span>}
          </button>
          <button type="button" className="btn btn-dark" onClick={() => onNavigate("chat")}>
            <Sparkles size={14} /> Open command center
          </button>
        </div>
      </div>

      <div className="kpi-grid">
        <div className="kpi">
          <div className="kpi-top">
            <span className="kpi-label">Published posts</span>
            <span className="kpi-icon blue">
              <PenTool />
            </span>
          </div>
          <div className="kpi-value">{stats.publishedPosts}</div>
          <div className="kpi-foot">
            {stats.draftPosts} drafts · {stats.scheduledPosts} scheduled
          </div>
        </div>

        <div className="kpi">
          <div className="kpi-top">
            <span className="kpi-label">Comments posted</span>
            <span className="kpi-icon violet">
              <MessageSquare />
            </span>
          </div>
          <div className="kpi-value">{stats.publishedComments}</div>
          <div className="kpi-foot">{stats.draftComments} awaiting review</div>
        </div>

        <div className="kpi">
          <div className="kpi-top">
            <span className="kpi-label">Applications</span>
            <span className="kpi-icon mint">
              <Briefcase />
            </span>
          </div>
          <div className="kpi-value">{stats.applications}</div>
          <div className="kpi-foot">
            {stats.preparing} preparing · {stats.interviews} interviews
          </div>
        </div>

        <div className="kpi">
          <div className="kpi-top">
            <span className="kpi-label">Average fit score</span>
            <span className="kpi-icon orange">
              <Target />
            </span>
          </div>
          <div className="kpi-value">
            {stats.avgFit}
            <small>%</small>
          </div>
          <div className="kpi-foot">{jobs.length} roles tracked</div>
        </div>
      </div>

      <div className="dash-grid">
        <section className="card">
          <div className="card-hd">
            <div>
              <h3 className="card-title">
                <Briefcase size={15} /> Application pipeline
              </h3>
              <p className="card-desc">Where every tracked role currently sits.</p>
            </div>
            <button type="button" className="link-btn" onClick={() => onNavigate("jobs")}>
              View all <ArrowUpRight />
            </button>
          </div>

          <div className="pipe-list">
            {PIPELINE.map((stage) => {
              const count = jobs.filter((job) => job.status === stage.name).length;
              return (
                <div className="pipe-row" key={stage.name}>
                  <span className="pipe-name">
                    <span className="dot" style={{ background: stage.color }} />
                    {stage.name}
                  </span>
                  <span className="pipe-track">
                    <span
                      className="pipe-fill"
                      style={{ width: count ? `${Math.max(6, (count / pipelineMax) * 100)}%` : "0%" }}
                    />
                  </span>
                  <span className="pipe-count">{count}</span>
                </div>
              );
            })}
          </div>
        </section>

        <section className="card">
          <div className="card-hd">
            <div>
              <h3 className="card-title">
                <Zap size={15} /> Agent output
              </h3>
              <p className="card-desc">Drafts created over the last 7 days.</p>
            </div>
            <span className="badge">{weekTotal} items</span>
          </div>

          <div className="spark">
            {days.map((day) => (
              <div className="spark-col" key={day.key}>
                <span
                  className={`spark-bar ${day.count === maxDay && day.count > 0 ? "hot" : ""}`}
                  style={{ height: `${Math.max(4, (day.count / maxDay) * 100)}%` }}
                  title={`${day.count} items`}
                />
                <span className="spark-label">{day.label}</span>
              </div>
            ))}
          </div>

          <div className="activity-list">
            {feed.length === 0 && <p className="muted" style={{ margin: 0 }}>No agent activity yet.</p>}
            {feed.map((item) => (
              <div className="activity-item" key={item.key}>
                <span className="activity-text">{item.text}</span>
                <span className="activity-time">{relativeTime(item.created_at)}</span>
                <span className={`badge ${statusTone(item.status)}`}>{prettyStatus(item.status)}</span>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="card" style={{ marginBottom: 12 }}>
        <div className="card-hd">
          <div>
            <h3 className="card-title">
              <Clock size={15} /> Waiting for your approval
            </h3>
            <p className="card-desc">Drafts stay private until you approve them.</p>
          </div>
          <button type="button" className="link-btn" onClick={() => onNavigate("content")}>
            Open studio <ArrowRight />
          </button>
        </div>

        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Item</th>
                <th>Type</th>
                <th>Status</th>
                <th className="nowrap">Created</th>
                <th className="num" />
              </tr>
            </thead>
            <tbody>
              {queue.length === 0 && (
                <tr className="empty-row">
                  <td colSpan={5}>Nothing waiting — every draft has been reviewed.</td>
                </tr>
              )}
              {queue.map((item) => (
                <tr key={item.key}>
                  <td>
                    <span className="cell-main">{item.title}</span>
                    <span className="cell-sub">{String(item.sub || "").slice(0, 90)}</span>
                  </td>
                  <td>
                    <span className={`badge ${item.tone}`}>
                      <span className="dot" />
                      {item.kind}
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${statusTone(item.status)}`}>{prettyStatus(item.status)}</span>
                  </td>
                  <td className="nowrap">{relativeTime(item.created_at)}</td>
                  <td className="num">
                    <button type="button" className="link-btn" onClick={() => onNavigate("content")}>
                      Review <ArrowRight />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className="dash-grid lower">
        <section className="card">
          <div className="card-hd">
            <div>
              <h3 className="card-title">
                <Target size={15} /> Top job matches
              </h3>
              <p className="card-desc">Ranked against your verified CV and target roles.</p>
            </div>
            <button type="button" className="link-btn" onClick={() => onNavigate("jobs")}>
              Pipeline <ArrowUpRight />
            </button>
          </div>

          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Role</th>
                  <th>Location</th>
                  <th>Fit</th>
                  <th>Status</th>
                  <th className="num" />
                </tr>
              </thead>
              <tbody>
                {topJobs.length === 0 && (
                  <tr className="empty-row">
                    <td colSpan={5}>No roles imported yet. Add one from the Jobs pipeline.</td>
                  </tr>
                )}
                {topJobs.map((job) => (
                  <tr key={job.id}>
                    <td>
                      <span className="cell-main">{job.title}</span>
                      <span className="cell-sub">{job.company || "Company not specified"}</span>
                    </td>
                    <td>{job.location || "—"}</td>
                    <td>
                      <div className="score">
                        <span className="score-bar">
                          <span
                            className={`score-fill ${scoreTone(job.match_score)}`}
                            style={{ width: `${Math.min(100, Number(job.match_score) || 0)}%` }}
                          />
                        </span>
                        <span className="score-value">{job.match_score}%</span>
                      </div>
                    </td>
                    <td>
                      <span className={`badge ${statusTone(job.status)}`}>{job.status}</span>
                    </td>
                    <td className="num">
                      {job.apply_url ? (
                        <a
                          className="link-btn"
                          href={job.apply_url}
                          target="_blank"
                          rel="noreferrer"
                          title="Open application link"
                        >
                          <ExternalLink />
                        </a>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="card">
          <div className="card-hd">
            <div>
              <h3 className="card-title">
                <CheckCircle2 size={15} /> Workspace readiness
              </h3>
              <p className="card-desc">Keep these complete for grounded drafts.</p>
            </div>
            <span className="badge">{readyPercent}%</span>
          </div>

          <div className="progress-meta">
            <span>
              <strong>{readyCount}</strong> of {readiness.length} complete
            </span>
          </div>
          <div className="bar" style={{ marginBottom: 14 }}>
            <span className="bar-fill" style={{ width: `${readyPercent}%` }} />
          </div>

          <div className="readiness">
            {readiness.map((item) => (
              <div className={`ready-row ${item.done ? "done" : ""}`} key={item.label}>
                {item.done ? <CheckCircle2 /> : <Circle />}
                {item.label}
                <span className={`badge ${item.done ? "ok" : "neutral"}`}>{item.hint}</span>
              </div>
            ))}
          </div>

          {!aiReady && (
            <p className="muted" style={{ marginTop: 12, marginBottom: 0, lineHeight: 1.5 }}>
              Start Ollama or switch providers in AI &amp; Privacy to let the agent draft.
            </p>
          )}
        </section>
      </div>
    </>
  );
}
