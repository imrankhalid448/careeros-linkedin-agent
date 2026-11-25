import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  Clock,
  ExternalLink,
  Loader2,
  MessageSquare,
  Pause,
  Play,
  RefreshCw,
  Rocket,
  Send,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { api } from "../api";

const STATUS_META = {
  scheduled: { label: "Queued", tone: "info" },
  draft: { label: "Draft", tone: "neutral" },
  published: { label: "Published", tone: "ok" },
  failed: { label: "Failed", tone: "err" },
  manual_required: { label: "Needs attention", tone: "warn" },
  missed: { label: "Missed", tone: "warn" },
  filling: { label: "Filling", tone: "neutral" },
};

function statusBadge(status) {
  const meta = STATUS_META[status] || STATUS_META.draft;
  return <span className={`badge ${meta.tone}`}>{meta.label}</span>;
}

export default function Autopilot({ onChanged, onNavigate }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  const load = useCallback(async () => {
    try {
      const next = await api.getAutopilot();
      setData(next);
      setError("");
      return next;
    } catch (err) {
      setError(err.message);
      return null;
    }
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, 15000);
    return () => clearInterval(timer);
  }, [load]);

  useEffect(() => {
    if (!pending) return undefined;
    const timer = setInterval(async () => {
      const next = await load();
      if (next && !next.generation.running) {
        setPending(false);
        setMsg("Draft queued. Autopilot will publish it at the scheduled time.");
        onChanged?.();
      }
    }, 5000);
    return () => clearInterval(timer);
  }, [pending, load, onChanged]);

  const update = async (payload, note) => {
    setBusy(true);
    setError("");
    try {
      const next = await api.updateAutopilot(payload);
      setData(next);
      if (note) setMsg(note);
      onChanged?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const toggle = () => {
    if (!data) return;
    update(
      { enabled: !data.enabled },
      data.enabled
        ? "Autopilot paused. Nothing new will be generated or published."
        : "Autopilot activated. Posts are being generated for the next slots."
    );
  };

  const generateNow = async () => {
    setBusy(true);
    setError("");
    try {
      const result = await api.queueAutopilot(1);
      setMsg(result.message || "Autopilot is drafting the next post.");
      setPending(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const publishNow = async (id) => {
    setBusy(true);
    setError("");
    try {
      const result = await api.publishPost(id);
      setMsg(result.message || "Post sent to LinkedIn.");
      await load();
      onChanged?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  if (!data) {
    return (
      <div className="card">
        <p className="muted">{error || "Loading autopilot…"}</p>
      </div>
    );
  }

  const publishedToday = data.counts.published_today ?? 0;
  const nextPost = data.next_post;

  return (
    <>
      <div className="page-head">
        <div>
          <div className="page-eyebrow">
            <span
              className="dot"
              style={{ background: data.enabled ? "var(--green)" : "var(--silver)" }}
            />
            Growth engine · {data.local_time}
          </div>
          <h1 className="page-title">Autopilot</h1>
          <p className="page-sub">
            A daily content strategy, posts generated ahead of time, and automatic publishing at the
            windows professional audiences actually read.
          </p>
        </div>
        <div className="head-actions">
          <button
            type="button"
            className="btn"
            onClick={generateNow}
            disabled={busy || data.generation.running}
          >
            {data.generation.running ? (
              <Loader2 className="spin" size={14} />
            ) : (
              <Sparkles size={14} />
            )}
            {data.generation.running ? "Drafting…" : "Generate now"}
          </button>
          <button
            type="button"
            className={`btn ${data.enabled ? "" : "btn-dark"}`}
            onClick={toggle}
            disabled={busy}
          >
            {data.enabled ? <Pause size={14} /> : <Play size={14} />}
            {data.enabled ? "Pause" : "Activate"}
          </button>
        </div>
      </div>

      {error && (
        <div className="banner">
          <span>{error}</span>
        </div>
      )}
      {msg && (
        <div className="banner">
          <span>{msg}</span>
          <button type="button" className="banner-close" onClick={() => setMsg("")}>
            dismiss
          </button>
        </div>
      )}

      <div className={`ap-hero ${data.enabled ? "" : "paused"}`}>
        <div className="ap-hero-main">
          <span className={`badge ${data.enabled ? "ok" : "neutral"}`}>
            <span className="dot" />
            {data.enabled ? "Active" : "Paused"}
          </span>
          <h2 className="ap-hero-title">
            {data.enabled ? "Posting on autopilot" : "Autopilot is paused"}
          </h2>
          <p className="ap-hero-sub">
            {data.enabled
              ? `${data.posts_per_day} posts per day across ${data.slots.length} slots. ` +
                (nextPost ? `Next: ${nextPost.pillar} · ${nextPost.local}.` : "Filling the next slots now.")
              : "Turn it back on to resume generating and publishing. Scheduled posts stay in the queue."}
          </p>
          {data.generation.running && (
            <p className="ap-working">
              <Loader2 className="spin" size={13} /> Drafting the next post with your local model. This
              usually takes about a minute.
            </p>
          )}
          {data.generation.last_error && (
            <p className="ap-error">
              <AlertTriangle size={13} /> {data.generation.last_error}
            </p>
          )}
        </div>
        <div className="ap-controls">
          <label className="ap-switch-row">
            <span>Auto-publish</span>
            <button
              type="button"
              role="switch"
              aria-checked={data.auto_publish}
              className={`ap-switch ${data.auto_publish ? "on" : ""}`}
              disabled={busy}
              onClick={() =>
                update(
                  { auto_publish: !data.auto_publish },
                  data.auto_publish
                    ? "Auto-publish off. New posts are saved as drafts; queued posts are unscheduled."
                    : "Auto-publish on. Queued posts will publish at their slot times."
                )
              }
            >
              <span />
            </button>
          </label>
          <label className="ap-field">
            <span>Posts per day</span>
            <select
              value={data.posts_per_day}
              disabled={busy}
              onChange={(event) =>
                update(
                  { posts_per_day: Number(event.target.value) },
                  `Cadence updated to ${event.target.value} posts per day.`
                )
              }
            >
              {[3, 4, 5].map((count) => (
                <option key={count} value={count}>
                  {count} posts
                </option>
              ))}
            </select>
          </label>
          <div className="ap-timezone">
            <Clock size={13} /> {data.timezone}
          </div>
        </div>
      </div>

      <div className="kpi-grid">
        <div className="kpi">
          <div className="kpi-top">
            <span className="kpi-label">Today&apos;s cadence</span>
            <span className="kpi-icon blue">
              <CalendarClock />
            </span>
          </div>
          <div className="kpi-value">
            {publishedToday}/{data.posts_per_day}
          </div>
          <div className="kpi-foot">posts published today</div>
        </div>
        <div className="kpi">
          <div className="kpi-top">
            <span className="kpi-label">Queued</span>
            <span className="kpi-icon">
              <Clock />
            </span>
          </div>
          <div className="kpi-value">{data.counts.queued}</div>
          <div className="kpi-foot">ready and scheduled</div>
        </div>
        <div className="kpi">
          <div className="kpi-top">
            <span className="kpi-label">Published this week</span>
            <span className="kpi-icon mint">
              <TrendingUp />
            </span>
          </div>
          <div className="kpi-value">{data.counts.published_7d}</div>
          <div className="kpi-foot">{data.counts.published_total} all-time on autopilot</div>
        </div>
        <div className="kpi">
          <div className="kpi-top">
            <span className="kpi-label">Posting streak</span>
            <span className="kpi-icon">
              <Activity />
            </span>
          </div>
          <div className="kpi-value">{data.counts.streak_days}d</div>
          <div className="kpi-foot">consecutive publishing days</div>
        </div>
      </div>

      <div className="ap-comment-card">
        <MessageSquare size={16} />
        <div>
          <strong>Comment replies</strong>
          <p>
            LinkedIn returns 403 for both reading comments and posting replies on this access tier; both
            need the Community Management API. Paste a comment in the reply desk and the agent writes a
            professional reply in your voice, ready to copy in one click.
          </p>
        </div>
        <button type="button" className="btn btn-sm" onClick={() => onNavigate?.("content")}>
          Open reply desk
        </button>
      </div>

      {data.errors.length > 0 && (
        <div className="card ap-errors">
          <div className="card-hd">
            <h3 className="card-title">
              <AlertTriangle size={15} /> Needs attention
            </h3>
          </div>
          {data.errors.map((item) => (
            <div className="ap-error-row" key={item.id}>
              <strong>{item.title}</strong>
              <span>{item.error}</span>
            </div>
          ))}
        </div>
      )}

      <div className="ap-grid">
        <div className="stack">
          <section className="card">
            <div className="card-hd">
              <div>
                <h3 className="card-title">
                  <CalendarClock size={15} /> Today&apos;s schedule
                </h3>
                <p className="card-desc">
                  Posts are drafted ahead of each slot, then published automatically.
                </p>
              </div>
              <span className="badge">{data.posts_per_day} slots</span>
            </div>
            <div className="ap-timeline">
              {data.today.map((slot) => (
                <div className="ap-slot" key={slot.time}>
                  <div className="ap-slot-time">{slot.label}</div>
                  <div className="ap-slot-body">
                    <div className="ap-slot-top">
                      <span className="ap-slot-pillar">{slot.pillar || "Open slot"}</span>
                      {statusBadge(slot.status)}
                    </div>
                    {slot.preview ? (
                      <p className="ap-slot-preview">{slot.preview}…</p>
                    ) : (
                      <p className="ap-slot-preview muted">
                        {slot.status === "missed"
                          ? "Slot passed before autopilot was active."
                          : "Autopilot will draft this post before the slot."}
                      </p>
                    )}
                  </div>
                  <div className="ap-slot-action">
                    {slot.url ? (
                      <a className="link-btn" href={slot.url} target="_blank" rel="noreferrer">
                        View <ExternalLink size={12} />
                      </a>
                    ) : slot.post_id ? (
                      <button
                        type="button"
                        className="link-btn"
                        onClick={() => onNavigate?.("content")}
                      >
                        Open
                      </button>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="card">
            <div className="card-hd">
              <div>
                <h3 className="card-title">
                  <Send size={15} /> Upcoming queue
                </h3>
                <p className="card-desc">
                  Generated posts with an editorial visual, waiting for their publishing window.
                </p>
              </div>
              <button type="button" className="btn btn-sm" onClick={load} disabled={busy}>
                <RefreshCw size={12} /> Refresh
              </button>
            </div>
            {data.queue.length === 0 ? (
              <p className="muted">
                Nothing queued yet. Autopilot fills the next slots automatically within a few minutes.
              </p>
            ) : (
              <div className="ap-queue">
                {data.queue.map((item) => (
                  <article className="ap-queue-item" key={item.id}>
                    <div className="ap-queue-top">
                      <strong>{item.title.replace("Autopilot · ", "")}</strong>
                      <span className="badge info">{item.local}</span>
                    </div>
                    {item.image_path && (
                      <img
                        className="ap-queue-img"
                        src={`/api/media/${item.image_path}`}
                        alt="Generated post visual"
                        loading="lazy"
                      />
                    )}
                    <p className="ap-queue-copy">{item.content.slice(0, 260)}…</p>
                    <div className="ap-queue-foot">
                      <button
                        type="button"
                        className="btn btn-sm"
                        onClick={() => publishNow(item.id)}
                        disabled={busy}
                      >
                        <Send size={12} /> Publish now
                      </button>
                      <button
                        type="button"
                        className="link-btn"
                        onClick={() => onNavigate?.("content")}
                      >
                        Edit in Posts
                      </button>
                      <span className="ap-queue-meta">{item.content.length} characters</span>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>

        <div className="stack">
          <section className="card">
            <div className="card-hd">
              <div>
                <h3 className="card-title">
                  <Rocket size={15} /> Daily strategy
                </h3>
                <p className="card-desc">{data.strategy.cadence}</p>
              </div>
            </div>
            <div className="ap-week">
              {data.strategy.weekly_plan.map((day) => (
                <div className="ap-week-row" key={day.date}>
                  <span className="ap-week-date">{day.date}</span>
                  <span className="ap-week-focus">{day.focus}</span>
                </div>
              ))}
            </div>
            <p className="ap-note">{data.strategy.best_times}</p>
          </section>

          <section className="card">
            <div className="card-hd">
              <div>
                <h3 className="card-title">
                  <Sparkles size={15} /> Content pillars
                </h3>
                <p className="card-desc">What the agent rotates through so the feed never repeats.</p>
              </div>
            </div>
            <div className="ap-pillars">
              {data.strategy.pillars.map((pillar) => (
                <div className="ap-pillar" key={pillar.key}>
                  <strong>{pillar.name}</strong>
                  <p>{pillar.summary}</p>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>

      <div className="ap-grid lower">
        <section className="card">
          <div className="card-hd">
            <div>
              <h3 className="card-title">
                <TrendingUp size={15} /> Growth playbook
              </h3>
              <p className="card-desc">
                What compounds followers and trust beyond posting volume.
              </p>
            </div>
          </div>
          <ol className="ap-playbook">
            <li>
              <strong>Publish daily, consistently.</strong> Four posts across different pillars beat five
              similar posts. The agent varies the angle, not just the wording.
            </li>
            <li>
              <strong>Reply in the first hour.</strong> Early comments decide distribution. When a comment
              arrives, paste it in <em>Posts &amp; Comments</em> and publish a specific reply in one click.
            </li>
            <li>
              <strong>Leave five thoughtful comments a day.</strong> Commenting on AI leaders&apos; posts
              exposes you to their audience. Use the reply drafter so the comment adds a real engineering
              perspective instead of praise.
            </li>
            <li>
              <strong>Make the profile convert.</strong> The post earns the visit; the headline, about
              section and featured project earn the follow. Keep Profile &amp; CV current.
            </li>
            <li>
              <strong>Review weekly, not hourly.</strong> Track followers, profile views and comment quality
              every Sunday, then adjust the pillars that underperform.
            </li>
          </ol>
          <p className="ap-note">
            <MessageSquare size={12} /> {data.strategy.engagement_note}
          </p>
        </section>

        <section className="card">
          <div className="card-hd">
            <div>
              <h3 className="card-title">
                <CheckCircle2 size={15} /> Published on autopilot
              </h3>
              <p className="card-desc">Recent posts the agent generated and shipped.</p>
            </div>
          </div>
          {data.recent.length === 0 ? (
            <p className="muted">No autopilot posts published yet. The first one will appear here.</p>
          ) : (
            <div className="ap-recent">
              {data.recent.map((item) => (
                <div className="ap-recent-row" key={item.id}>
                  <div>
                    <strong>{item.title.replace("Autopilot · ", "")}</strong>
                    <p>{item.content}…</p>
                  </div>
                  {item.url && (
                    <a className="link-btn" href={item.url} target="_blank" rel="noreferrer">
                      <ExternalLink size={12} />
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </>
  );
}
