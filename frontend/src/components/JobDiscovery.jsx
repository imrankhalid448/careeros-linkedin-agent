import { useEffect, useMemo, useState } from "react";
import {
  ExternalLink,
  MapPin,
  Plus,
  Radio,
  RefreshCw,
  Search,
  X,
} from "lucide-react";
import { api } from "../api";
import { relativeTime, scoreTone } from "../utils";

export default function JobDiscovery({ pipelineJobs = [], onTracked }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [query, setQuery] = useState("");
  const [queryInput, setQueryInput] = useState("");
  const [location, setLocation] = useState("");
  const [locationInput, setLocationInput] = useState("");
  const [sourceFilter, setSourceFilter] = useState("All");
  const [onlyRelevant, setOnlyRelevant] = useState(false);
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [trackingId, setTrackingId] = useState("");
  const [trackedIds, setTrackedIds] = useState([]);

  const load = async ({ force = false, nextQuery = query, nextLocation = location } = {}) => {
    setLoading(true);
    setError("");
    try {
      const res = await api.discoverJobs({
        q: nextQuery,
        location: nextLocation,
        limit: 100,
        refresh: force,
      });
      setData(res);
      setQuery(nextQuery);
      setLocation(nextLocation);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const track = async (job) => {
    setTrackingId(job.id);
    setMessage("");
    try {
      const res = await api.trackJob({
        title: job.title,
        company: job.company,
        location: job.location,
        work_mode: job.work_mode,
        apply_url: job.url,
        description: job.description,
        source: job.source,
      });
      setTrackedIds((prev) => [...new Set([...prev, job.id])]);
      setMessage(res.message);
      onTracked?.();
    } catch (err) {
      setMessage(err.message);
    } finally {
      setTrackingId("");
    }
  };

  const jobs = data?.jobs || [];
  const sources = data?.sources || [];

  const filtered = useMemo(
    () =>
      jobs.filter((job) => {
        if (sourceFilter !== "All" && job.source !== sourceFilter) return false;
        if (onlyRelevant && job.relevance < 20) return false;
        if (remoteOnly && job.work_mode !== "remote") return false;
        return true;
      }),
    [jobs, sourceFilter, onlyRelevant, remoteOnly]
  );

  const pipelineUrls = useMemo(
    () => new Set(pipelineJobs.map((job) => job.apply_url).filter(Boolean)),
    [pipelineJobs]
  );

  return (
    <>
      <section className="card" style={{ marginBottom: 12 }}>
        <div className="card-hd">
          <div>
            <h3 className="card-title">
              <Radio size={15} /> Live relevant jobs
            </h3>
            <p className="card-desc">
              Real, currently-open roles from public job feeds, scored against your target roles and skills.
            </p>
          </div>
          <span className="badge ok">
            <span className="live-dot" /> {data ? `${data.total} matches` : "Connecting"}
          </span>
        </div>

        <form
          className="discover-toolbar"
          onSubmit={(event) => {
            event.preventDefault();
            load({ nextQuery: queryInput.trim(), nextLocation: locationInput.trim() });
          }}
        >
          <div className="field">
            <label className="field-label">
              <Search size={12} /> Keywords
            </label>
            <input
              value={queryInput}
              onChange={(event) => setQueryInput(event.target.value)}
              placeholder="AI Engineer, Machine Learning, Computer Vision…"
            />
          </div>
          <div className="field">
            <label className="field-label">
              <MapPin size={12} /> Location
            </label>
            <input
              value={locationInput}
              onChange={(event) => setLocationInput(event.target.value)}
              placeholder="Worldwide / Pakistan / Remote"
            />
          </div>
          <button className="btn btn-dark" type="submit" disabled={loading}>
            {loading ? <span className="spinner light" /> : <Search size={14} />} Search
          </button>
          <button
            className="btn"
            type="button"
            disabled={loading}
            onClick={() => load({ force: true })}
            title="Fetch fresh postings"
          >
            <RefreshCw size={14} className={loading ? "spin" : ""} /> Refresh
          </button>
        </form>

        <div className="source-row">
          <button
            type="button"
            className={`source-chip ${sourceFilter === "All" ? "active" : ""}`}
            onClick={() => setSourceFilter("All")}
          >
            All sources · {jobs.length}
          </button>
          {sources.map((source) => (
            <button
              type="button"
              key={source.name}
              className={`source-chip ${source.ok ? "" : "err"} ${
                sourceFilter === source.name ? "active" : ""
              }`}
              onClick={() => setSourceFilter(source.name)}
              title={source.ok ? `${source.name} returned ${source.count} postings` : source.error}
              disabled={!source.ok}
            >
              <span className="dot" /> {source.name} · {source.count}
            </button>
          ))}
          {data?.fetched_at && <span className="source-updated">Updated {relativeTime(data.fetched_at)}</span>}
        </div>

        <div className="chip-row" style={{ marginTop: 10 }}>
          <button
            type="button"
            className={`chip ${onlyRelevant ? "active" : ""}`}
            onClick={() => setOnlyRelevant((value) => !value)}
          >
            AI/ML only <span className="chip-count">{data?.relevant_count ?? 0}</span>
          </button>
          <button
            type="button"
            className={`chip ${remoteOnly ? "active" : ""}`}
            onClick={() => setRemoteOnly((value) => !value)}
          >
            Remote only <span className="chip-count">{data?.remote_count ?? 0}</span>
          </button>
        </div>

        {data && (
          <p className="discover-note">
            Scanned {data.scanned} postings across {sources.filter((source) => source.ok).length} live feeds and
            ranked {data.total} roles by relevance. LinkedIn does not expose job search to developer apps —
            import a LinkedIn job by URL with <strong>Import job</strong>.
          </p>
        )}
      </section>

      {message && (
        <div className="banner">
          <span>{message}</span>
          <button type="button" className="banner-close" onClick={() => setMessage("")} aria-label="Dismiss">
            <X size={14} />
          </button>
        </div>
      )}
      {error && (
        <div className="banner">
          <span>{error}</span>
          <button type="button" className="banner-close" onClick={() => setError("")} aria-label="Dismiss">
            <X size={14} />
          </button>
        </div>
      )}

      <section className="card">
        <div className="card-hd">
          <div>
            <h3 className="card-title">
              <Radio size={15} /> {sourceFilter === "All" ? "All live matches" : `${sourceFilter} matches`}
            </h3>
            <p className="card-desc">
              {query ? `Search: “${query}” · ` : "Scored against your confirmed profile · "}
              {filtered.length} roles shown
            </p>
          </div>
          {data?.profile_roles?.length > 0 && (
            <div className="chip-row">
              {data.profile_roles.slice(0, 3).map((role) => (
                <span className="chip" key={role}>
                  {role}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Role</th>
                <th>Company</th>
                <th>Location</th>
                <th>Relevance</th>
                <th>Source</th>
                <th className="nowrap">Posted</th>
                <th className="num" />
              </tr>
            </thead>
            <tbody>
              {loading && jobs.length === 0 && (
                <tr className="empty-row">
                  <td colSpan={7}>Fetching live postings from Remotive, Arbeitnow, Jobicy and RemoteOK…</td>
                </tr>
              )}
              {!loading && filtered.length === 0 && (
                <tr>
                  <td colSpan={7}>
                    <div className="discover-empty">
                      <strong>No live matches for this search.</strong>
                      Try a broader keyword (for example “AI” or “Python”), clear the location filter or turn
                      off AI/ML-only and Remote-only, then refresh.
                    </div>
                  </td>
                </tr>
              )}
              {filtered.map((job) => {
                const tracked = trackedIds.includes(job.id) || pipelineUrls.has(job.url);
                return (
                  <tr key={job.id}>
                    <td>
                      <div className="job-title-cell">
                        <span className="cell-main">{job.title}</span>
                        <span className="cell-sub">
                          {[job.salary, job.job_type, job.work_mode].filter(Boolean).join(" · ") ||
                            "Details at source"}
                        </span>
                      </div>
                    </td>
                    <td>{job.company || "—"}</td>
                    <td>{job.location || "—"}</td>
                    <td>
                      <div className="score">
                        <span className="score-bar">
                          <span
                            className={`score-fill ${scoreTone(job.relevance)}`}
                            style={{ width: `${Math.min(100, job.relevance)}%` }}
                          />
                        </span>
                        <span className="score-value">{job.relevance}%</span>
                      </div>
                    </td>
                    <td>
                      <span className="badge">{job.source}</span>
                    </td>
                    <td className="nowrap">{relativeTime(job.posted_at)}</td>
                    <td className="num">
                      <div className="job-actions">
                        <button
                          className={`btn btn-sm ${tracked ? "" : "btn-dark"}`}
                          type="button"
                          disabled={tracked || trackingId === job.id}
                          onClick={() => track(job)}
                          title={tracked ? "Already in your pipeline" : "Add to pipeline"}
                        >
                          {trackingId === job.id ? (
                            <span className="spinner light" />
                          ) : tracked ? (
                            "Tracked"
                          ) : (
                            <Plus size={13} />
                          )}
                          {!tracked && trackingId !== job.id && "Track"}
                        </button>
                        {job.url && (
                          <a
                            className="btn btn-sm"
                            href={job.url}
                            target="_blank"
                            rel="noreferrer"
                            title="Open the original posting"
                          >
                            <ExternalLink size={13} />
                          </a>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <p className="discover-note">
          Job data from{" "}
          <a href="https://remotive.com" target="_blank" rel="noreferrer">
            Remotive
          </a>
          ,{" "}
          <a href="https://www.arbeitnow.com" target="_blank" rel="noreferrer">
            Arbeitnow
          </a>
          ,{" "}
          <a href="https://jobicy.com" target="_blank" rel="noreferrer">
            Jobicy
          </a>
          ,{" "}
          <a href="https://remoteok.com" target="_blank" rel="noreferrer">
            RemoteOK
          </a>{" "}
          and{" "}
          <a href="https://himalayas.app" target="_blank" rel="noreferrer">
            Himalayas
          </a>
          . Tracked roles are saved without an AI assessment; open the pipeline and prepare an application when
          you are ready.
        </p>
      </section>
    </>
  );
}
