import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Briefcase,
  LayoutDashboard,
  PenTool,
  Plug,
  Rocket,
  ShieldCheck,
  Sparkles,
  UserCheck,
} from "lucide-react";
import { api } from "./api";
import { initials } from "./utils";
import Dashboard from "./components/Dashboard";
import ChatWorkspace from "./components/ChatWorkspace";
import ProfileManager from "./components/ProfileManager";
import ContentStudio from "./components/ContentStudio";
import Autopilot from "./components/Autopilot";
import JobTracker from "./components/JobTracker";
import ConnectorsPanel from "./components/ConnectorsPanel";
import SettingsPanel from "./components/SettingsPanel";

const NAV = [
  {
    group: "Workspace",
    items: [
      { id: "overview", label: "Overview", icon: LayoutDashboard },
      { id: "chat", label: "Command Center", icon: Sparkles },
    ],
  },
  {
    group: "Content & Growth",
    items: [
      { id: "autopilot", label: "Growth Autopilot", icon: Rocket },
      { id: "content", label: "Posts & Comments", icon: PenTool, badge: "content" },
      { id: "jobs", label: "Jobs & Pipeline", icon: Briefcase, badge: "jobs" },
    ],
  },
  {
    group: "Knowledge",
    items: [{ id: "profile", label: "Profile & CV", icon: UserCheck }],
  },
  {
    group: "System",
    items: [
      { id: "connectors", label: "Connectors", icon: Plug },
      { id: "settings", label: "AI & Privacy", icon: ShieldCheck },
    ],
  },
];

const TITLES = Object.fromEntries(NAV.flatMap((group) => group.items.map((item) => [item.id, item.label])));

export default function App() {
  const [tab, setTab] = useState("overview");
  const [profile, setProfile] = useState(null);
  const [posts, setPosts] = useState([]);
  const [comments, setComments] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [notes, setNotes] = useState([]);
  const [connectors, setConnectors] = useState([]);
  const [settings, setSettings] = useState(null);

  const refresh = useCallback(async () => {
    const results = await Promise.allSettled([
      api.getProfile(),
      api.getPosts(),
      api.getComments(),
      api.getJobs(),
      api.getNotes(),
      api.getConnectors(),
      api.getSettings(),
    ]);
    const [profileRes, postsRes, commentsRes, jobsRes, notesRes, connectorsRes, settingsRes] = results;
    if (profileRes.status === "fulfilled") setProfile(profileRes.value);
    if (postsRes.status === "fulfilled") setPosts(postsRes.value);
    if (commentsRes.status === "fulfilled") setComments(commentsRes.value);
    if (jobsRes.status === "fulfilled") setJobs(jobsRes.value);
    if (notesRes.status === "fulfilled") setNotes(notesRes.value);
    if (connectorsRes.status === "fulfilled") setConnectors(connectorsRes.value);
    if (settingsRes.status === "fulfilled") setSettings(settingsRes.value);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const linkedin = connectors.find((connector) => connector.platform === "linkedin");
  const linkedinConnected = Boolean(linkedin?.connected);
  const aiRunning = settings?.is_external
    ? Boolean(settings?.has_external_api_key)
    : Boolean(settings?.ollama_status?.running);
  const aiLabel = settings?.is_external
    ? settings?.external_ai_model || "External API"
    : settings?.ollama_model || "qwen2.5:7b";

  const counts = useMemo(
    () => ({
      content:
        posts.filter((post) => ["draft", "scheduled"].includes(post.status)).length +
        comments.filter((comment) => ["draft", "manual_required"].includes(comment.status)).length,
      jobs: jobs.filter((job) => ["Saved", "Preparing"].includes(job.status)).length,
    }),
    [posts, comments, jobs]
  );

  const displayName = profile?.full_name?.trim() || "Your workspace";
  const displayRole = profile?.headline?.trim() || "LinkedIn agent workspace";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-ring">
            <div className="brand-mark">
              <Sparkles size={15} />
            </div>
          </div>
          <div className="brand-text">
            <div className="brand-name">CareerOS</div>
            <div className="brand-sub">LinkedIn Agent CRM</div>
          </div>
        </div>

        <div className="ws-card">
          <span className="avatar">{initials(profile?.full_name)}</span>
          <div className="ws-meta">
            <div className="ws-name">{displayName}</div>
            <div className="ws-sub">Personal workspace</div>
          </div>
        </div>

        {NAV.map((group) => (
          <div className="nav-group" key={group.group}>
            <p className="nav-group-label">{group.group}</p>
            {group.items.map((item) => {
              const Icon = item.icon;
              const badgeValue = item.badge ? counts[item.badge] : 0;
              return (
                <button
                  key={item.id}
                  type="button"
                  className={`nav-btn ${tab === item.id ? "active" : ""}`}
                  onClick={() => setTab(item.id)}
                  title={item.label}
                >
                  <Icon size={15} />
                  <span>{item.label}</span>
                  {badgeValue > 0 && <span className="nav-count">{badgeValue}</span>}
                </button>
              );
            })}
          </div>
        ))}

        <div className="sidebar-foot">
          <div className="engine-card">
            <div className="engine-row">
              <span className="dot" style={{ background: aiRunning ? "var(--green)" : "var(--silver)" }} />
              Agent engine
              <span className="badge">{settings?.is_external ? "External" : "Local"}</span>
            </div>
            <div className="engine-name">{aiLabel}</div>
            <div className="engine-note">
              {settings?.is_external
                ? "Drafts are sent to your configured external API."
                : "Private by default. Nothing leaves this laptop."}
            </div>
          </div>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="crumbs">
            <span>Workspace</span>
            <span className="crumb-sep">/</span>
            <span className="crumb-current">{TITLES[tab] || "Overview"}</span>
          </div>

          <div className="topbar-right">
            <span className="status-pill">
              <span
                className="dot"
                style={{ background: linkedinConnected ? "var(--green)" : "var(--tangerine)" }}
              />
              LinkedIn <strong>{linkedinConnected ? "Connected" : "Offline"}</strong>
            </span>
            <span className="status-pill ai">
              <span className="dot" style={{ background: aiRunning ? "var(--lavender)" : "var(--silver)" }} />
              AI <strong>{settings?.is_external ? "External" : "Local"}</strong>
            </span>
            <span className="divider-v" />
            <div className="user-chip">
              <span className="avatar">{initials(profile?.full_name)}</span>
              <div className="user-meta">
                <div className="user-name">{profile?.full_name?.trim() || "You"}</div>
                <div className="user-role">Owner</div>
              </div>
            </div>
          </div>
        </header>

        <main className="main-area">
          {tab === "overview" && (
            <Dashboard
              profile={profile}
              posts={posts}
              comments={comments}
              jobs={jobs}
              notes={notes}
              settings={settings}
              linkedin={linkedin}
              onNavigate={setTab}
            />
          )}
          {tab === "chat" && <ChatWorkspace onOpenJobs={() => setTab("jobs")} onChanged={refresh} />}
          {tab === "profile" && <ProfileManager onChanged={refresh} />}
          {tab === "autopilot" && <Autopilot onChanged={refresh} onNavigate={setTab} />}
          {tab === "content" && <ContentStudio onChanged={refresh} />}
          {tab === "jobs" && <JobTracker onChanged={refresh} />}
          {tab === "connectors" && <ConnectorsPanel onStatusChange={refresh} />}
          {tab === "settings" && <SettingsPanel onSaved={refresh} />}
        </main>
      </div>
    </div>
  );
}
