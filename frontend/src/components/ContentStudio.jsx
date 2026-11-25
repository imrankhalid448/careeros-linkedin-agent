import { useEffect, useState } from "react";
import {
  Check,
  ChevronDown,
  ChevronUp,
  Clock,
  Copy,
  ExternalLink,
  Image as ImageIcon,
  MessageCircle,
  PenTool,
  Send,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { api } from "../api";
import { prettyStatus, relativeTime, statusTone } from "../utils";

const POST_FILTERS = ["all", "draft", "scheduled", "published"];

export default function ContentStudio({ onChanged }) {
  const [tab, setTab] = useState("posts");
  const [notes, setNotes] = useState([]);
  const [posts, setPosts] = useState([]);
  const [comments, setComments] = useState([]);
  const [postForm, setPostForm] = useState({
    source_type: "project_note",
    project_note_id: "",
    github_url: "",
    idea: "",
  });
  const [commentForm, setCommentForm] = useState({ target_url: "", source_post_text: "", intent: "" });
  const [postFilter, setPostFilter] = useState("all");
  const [expanded, setExpanded] = useState("");
  const [postEdits, setPostEdits] = useState({});
  const [commentEdits, setCommentEdits] = useState({});
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [copiedId, setCopiedId] = useState("");

  const load = async () => {
    const [noteList, postList, commentList] = await Promise.all([
      api.getNotes(),
      api.getPosts(),
      api.getComments(),
    ]);
    setNotes(noteList);
    setPosts(postList);
    setComments(commentList);
  };

  useEffect(() => {
    load();
  }, []);

  const copyText = (id, text) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(""), 1800);
  };

  const refreshAll = () => {
    load();
    onChanged?.();
  };

  const createPost = async (event) => {
    event.preventDefault();
    setBusy(true);
    setMsg("Drafting a LinkedIn post in your authentic voice…");
    try {
      await api.generatePost({
        platform: "linkedin",
        source_type: postForm.source_type,
        project_note_id: postForm.project_note_id ? Number(postForm.project_note_id) : null,
        github_url: postForm.github_url,
        idea: postForm.idea,
      });
      setMsg("Draft generated. Review it in the queue, then approve to publish.");
      refreshAll();
    } catch (err) {
      setMsg(err.message);
    } finally {
      setBusy(false);
    }
  };

  const createComment = async (event) => {
    event.preventDefault();
    setBusy(true);
    setMsg("");
    try {
      const res = await api.generateComment(commentForm);
      setMsg(res.needs_more_context ? res.message : "Comment draft ready for your approval.");
      if (!res.needs_more_context) refreshAll();
    } catch (err) {
      setMsg(err.message);
    } finally {
      setBusy(false);
    }
  };

  const savePost = async (post) => {
    setBusy(true);
    try {
      await api.updatePost(post.id, {
        content: postEdits[post.id] ?? post.content,
        scheduled_for: post.scheduled_for || "",
      });
      setMsg("Draft and schedule saved.");
      refreshAll();
    } catch (err) {
      setMsg(err.message);
    } finally {
      setBusy(false);
    }
  };

  const publishPost = async (post) => {
    setBusy(true);
    try {
      await api.updatePost(post.id, { content: postEdits[post.id] ?? post.content });
      const res = await api.publishPost(post.id);
      setMsg(res.message);
      refreshAll();
    } catch (err) {
      setMsg(err.message);
    } finally {
      setBusy(false);
    }
  };

  const generateImage = async (post) => {
    setBusy(true);
    setMsg("Generating a visual for your post…");
    try {
      const res = await api.generatePostImage(post.id);
      setMsg(`Image ready (${res.image_provider}).`);
      refreshAll();
    } catch (err) {
      setMsg(err.message);
    } finally {
      setBusy(false);
    }
  };

  const uploadImage = async (post, file) => {
    if (!file) return;
    setBusy(true);
    try {
      await api.uploadPostImage(post.id, file);
      setMsg("Image attached to post.");
      refreshAll();
    } catch (err) {
      setMsg(err.message);
    } finally {
      setBusy(false);
    }
  };

  const removeImage = async (post) => {
    setBusy(true);
    try {
      await api.removePostImage(post.id);
      setMsg("Image removed.");
      refreshAll();
    } catch (err) {
      setMsg(err.message);
    } finally {
      setBusy(false);
    }
  };

  const saveComment = async (comment) => {
    setBusy(true);
    try {
      await api.updateComment(comment.id, commentEdits[comment.id] ?? comment.draft_reply);
      setMsg("Reply draft saved.");
      refreshAll();
    } catch (err) {
      setMsg(err.message);
    } finally {
      setBusy(false);
    }
  };

  const publishComment = async (comment) => {
    setBusy(true);
    try {
      await api.updateComment(comment.id, commentEdits[comment.id] ?? comment.draft_reply);
      const res = await api.publishComment(comment.id);
      setMsg(res.message);
      refreshAll();
    } catch (err) {
      setMsg(err.message);
    } finally {
      setBusy(false);
    }
  };

  const filteredPosts = postFilter === "all" ? posts : posts.filter((post) => post.status === postFilter);
  const drafts = posts.filter((post) => post.status === "draft").length;
  const scheduled = posts.filter((post) => post.status === "scheduled").length;
  const published = posts.filter((post) => post.status === "published").length;

  const toggle = (key) => setExpanded(expanded === key ? "" : key);

  return (
    <>
      <div className="page-head">
        <div>
          <div className="page-eyebrow">
            <PenTool size={12} /> Content studio
          </div>
          <h2 className="page-title">Posts &amp; comments</h2>
          <p className="page-sub">
            Draft, schedule and approve LinkedIn content. Autopilot posts ship with a generated visual;
            new drafts get one automatically. Comment replies are drafted for one-click copying because
            LinkedIn restricts direct comment APIs.
          </p>
        </div>
        <div className="head-actions">
          <div className="segmented">
            <button
              type="button"
              className={tab === "posts" ? "active" : ""}
              onClick={() => setTab("posts")}
            >
              <PenTool /> Posts
            </button>
            <button
              type="button"
              className={tab === "comments" ? "active" : ""}
              onClick={() => setTab("comments")}
            >
              <MessageCircle /> Comments
            </button>
          </div>
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

      <div className="studio-stats">
        <div className="mini-stat">
          <span className="mini-stat-icon">
            <PenTool />
          </span>
          <div>
            <div className="mini-stat-value">{tab === "posts" ? drafts : comments.filter((c) => c.status === "draft").length}</div>
            <div className="mini-stat-label">{tab === "posts" ? "Drafts awaiting review" : "Reply drafts"}</div>
          </div>
        </div>
        <div className="mini-stat">
          <span className="mini-stat-icon">
            <Clock />
          </span>
          <div>
            <div className="mini-stat-value">
              {tab === "posts" ? scheduled : comments.filter((c) => ["manual_required", "failed"].includes(c.status)).length}
            </div>
            <div className="mini-stat-label">
              {tab === "posts" ? "Scheduled posts" : "Needs manual posting"}
            </div>
          </div>
        </div>
        <div className="mini-stat">
          <span className="mini-stat-icon">
            <Check />
          </span>
          <div>
            <div className="mini-stat-value">
              {tab === "posts" ? published : comments.filter((c) => c.status === "published").length}
            </div>
            <div className="mini-stat-label">{tab === "posts" ? "Published posts" : "Published replies"}</div>
          </div>
        </div>
      </div>

      <div className="page-grid compose">
        {tab === "posts" ? (
          <form className="card" onSubmit={createPost}>
            <div className="card-hd">
              <div>
                <h3 className="card-title">
                  <PenTool size={15} /> Create a post
                </h3>
                <p className="card-desc">Ground the draft in a project note, link or rough angle.</p>
              </div>
            </div>

            <div className="field">
              <label className="field-label">Source material</label>
              <select
                value={postForm.source_type}
                onChange={(event) => setPostForm({ ...postForm, source_type: event.target.value })}
              >
                <option value="project_note">Project note</option>
                <option value="github">GitHub link + context</option>
                <option value="idea">Rough idea</option>
              </select>
            </div>

            {postForm.source_type === "project_note" && (
              <div className="field">
                <label className="field-label">Project note</label>
                <select
                  value={postForm.project_note_id}
                  onChange={(event) => setPostForm({ ...postForm, project_note_id: event.target.value })}
                >
                  <option value="">Choose a project note…</option>
                  {notes.map((note) => (
                    <option key={note.id} value={note.id}>
                      {note.title}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="field">
              <label className="field-label">GitHub / reference URL</label>
              <input
                value={postForm.github_url}
                onChange={(event) => setPostForm({ ...postForm, github_url: event.target.value })}
                placeholder="https://github.com/…"
              />
            </div>

            <div className="field">
              <label className="field-label">Key points / angle</label>
              <textarea
                value={postForm.idea}
                onChange={(event) => setPostForm({ ...postForm, idea: event.target.value })}
                placeholder="What problem did you solve, what did you benchmark, what did you learn?"
              />
            </div>

            <button className="btn btn-dark btn-block" type="submit" disabled={busy}>
              <PenTool size={14} /> {busy ? "Working…" : "Generate draft"}
            </button>
          </form>
        ) : (
          <form className="card" onSubmit={createComment}>
            <div className="card-hd">
              <div>
                <h3 className="card-title">
                  <MessageCircle size={15} /> Draft a reply
                </h3>
                <p className="card-desc">Paste the post or comment you want to respond to.</p>
              </div>
            </div>

            <div className="field">
              <label className="field-label">LinkedIn post URL</label>
              <input
                value={commentForm.target_url}
                onChange={(event) => setCommentForm({ ...commentForm, target_url: event.target.value })}
                placeholder="https://www.linkedin.com/feed/update/urn:li:activity:…"
              />
            </div>

            <div className="field">
              <label className="field-label">Post or comment text</label>
              <textarea
                value={commentForm.source_post_text}
                onChange={(event) =>
                  setCommentForm({ ...commentForm, source_post_text: event.target.value })
                }
                placeholder="Paste the post or comment you are replying to…"
              />
            </div>

            <div className="field">
              <label className="field-label">Your angle / intent</label>
              <input
                value={commentForm.intent}
                onChange={(event) => setCommentForm({ ...commentForm, intent: event.target.value })}
                placeholder="e.g. Share a benchmark observation on inference latency"
              />
            </div>

            <p className="muted" style={{ marginTop: 10 }}>
              LinkedIn returns 403 when apps read comments or post replies on this access tier; both need
              the Community Management API. Paste the comment here and the agent writes the reply in your
              voice, ready to copy in one click.
            </p>
            <button className="btn btn-dark btn-block" type="submit" disabled={busy}>
              <MessageCircle size={14} /> {busy ? "Working…" : "Draft reply"}
            </button>
          </form>
        )}

        <section className="card">
          <div className="card-hd">
            <div>
              <h3 className="card-title">
                {tab === "posts" ? <PenTool size={15} /> : <MessageCircle size={15} />}
                {tab === "posts" ? "Post queue" : "Reply queue"}
              </h3>
              <p className="card-desc">
                {tab === "posts"
                  ? "Click a row to edit the copy, schedule it or approve publishing."
                  : "Click a row to refine the reply before approving it."}
              </p>
            </div>
            {tab === "posts" && (
              <div className="chip-row">
                {POST_FILTERS.map((filter) => (
                  <button
                    type="button"
                    key={filter}
                    className={`chip ${postFilter === filter ? "active" : ""}`}
                    onClick={() => setPostFilter(filter)}
                  >
                    {filter === "all" ? "All" : prettyStatus(filter)}
                    <span className="chip-count">
                      {filter === "all" ? posts.length : posts.filter((post) => post.status === filter).length}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {tab === "posts" ? (
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Post</th>
                    <th>Status</th>
                    <th>Schedule</th>
                    <th className="nowrap">Created</th>
                    <th className="num" />
                  </tr>
                </thead>
                <tbody>
                  {filteredPosts.length === 0 && (
                    <tr className="empty-row">
                      <td colSpan={5}>No posts in this state yet.</td>
                    </tr>
                  )}
                  {filteredPosts.map((post) => {
                    const isOpen = expanded === `post-${post.id}`;
                    const value = postEdits[post.id] ?? post.content;
                    const isPublished = post.status === "published";
                    return (
                      <PostRow
                        key={post.id}
                        post={post}
                        isOpen={isOpen}
                        value={value}
                        isPublished={isPublished}
                        busy={busy}
                        copiedId={copiedId}
                        onToggle={() => toggle(`post-${post.id}`)}
                        onChange={(next) => setPostEdits({ ...postEdits, [post.id]: next })}
                        onSchedule={(next) =>
                          setPosts((prev) =>
                            prev.map((item) => (item.id === post.id ? { ...item, scheduled_for: next } : item))
                          )
                        }
                        onSave={() => savePost(post)}
                        onPublish={() => publishPost(post)}
                        onCopy={() => copyText(`p-${post.id}`, value)}
                        onGenerateImage={() => generateImage(post)}
                        onUploadImage={(file) => uploadImage(post, file)}
                        onRemoveImage={() => removeImage(post)}
                      />
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Reply</th>
                    <th>Status</th>
                    <th className="nowrap">Created</th>
                    <th className="num" />
                  </tr>
                </thead>
                <tbody>
                  {comments.length === 0 && (
                    <tr className="empty-row">
                      <td colSpan={4}>No reply drafts yet.</td>
                    </tr>
                  )}
                  {comments.map((comment) => {
                    const isOpen = expanded === `comment-${comment.id}`;
                    const value = commentEdits[comment.id] ?? comment.draft_reply;
                    const isPublished = comment.status === "published";
                    return (
                      <CommentRow
                        key={comment.id}
                        comment={comment}
                        isOpen={isOpen}
                        value={value}
                        isPublished={isPublished}
                        busy={busy}
                        copiedId={copiedId}
                        onToggle={() => toggle(`comment-${comment.id}`)}
                        onChange={(next) => setCommentEdits({ ...commentEdits, [comment.id]: next })}
                        onSave={() => saveComment(comment)}
                        onPublish={() => publishComment(comment)}
                        onCopy={() => copyText(`c-${comment.id}`, value)}
                      />
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </>
  );
}

function PostRow({
  post,
  isOpen,
  value,
  isPublished,
  busy,
  copiedId,
  onToggle,
  onChange,
  onSchedule,
  onSave,
  onPublish,
  onCopy,
  onGenerateImage,
  onUploadImage,
  onRemoveImage,
}) {
  return (
    <>
      <tr className="post-row" onClick={onToggle}>
        <td>
          <span className="cell-main">{post.title || "Untitled post"}</span>
          <span className="cell-sub">{String(value).slice(0, 110)}</span>
        </td>
        <td>
          <span className={`badge ${statusTone(post.status)}`}>{prettyStatus(post.status)}</span>
        </td>
        <td className="nowrap">{post.scheduled_for || "—"}</td>
        <td className="nowrap">{relativeTime(post.created_at)}</td>
        <td className="num">
          <button type="button" className="link-btn" onClick={(event) => { event.stopPropagation(); onToggle(); }}>
            {isOpen ? <ChevronUp /> : <ChevronDown />}
          </button>
        </td>
      </tr>
      {isOpen && (
        <tr className="post-expand">
          <td colSpan={5}>
            <div className="post-editor">
              <textarea value={value} disabled={isPublished} onChange={(event) => onChange(event.target.value)} />

              {post.image_path && (
                <img src={`/api/media/${post.image_path}`} alt="Post visual" className="img-preview" />
              )}

              <div className="schedule-row">
                <div className="field" style={{ margin: 0 }}>
                  <label className="field-label">
                    <Clock size={12} /> Schedule (ISO UTC, optional)
                  </label>
                  <input
                    value={post.scheduled_for || ""}
                    disabled={isPublished}
                    onChange={(event) => onSchedule(event.target.value)}
                    placeholder="2026-11-24T09:00:00Z"
                  />
                </div>
                <button className="btn btn-sm" type="button" disabled={isPublished || busy} onClick={onSave}>
                  Save draft
                </button>
              </div>

              <div className="post-editor-foot">
                <div className="row" style={{ gap: 6 }}>
                  <button
                    className="btn btn-dark btn-sm"
                    type="button"
                    disabled={isPublished || busy}
                    onClick={onPublish}
                  >
                    <Send size={13} /> {isPublished ? "Published" : "Approve & publish"}
                  </button>
                  {!isPublished && (
                    <>
                      <button className="btn btn-sm" type="button" disabled={busy} onClick={onGenerateImage}>
                        <ImageIcon size={13} /> Generate visual
                      </button>
                      <label className="btn btn-sm file-btn">
                        <Upload size={13} /> Upload
                        <input
                          type="file"
                          className="hidden-input"
                          accept=".png,.jpg,.jpeg,.webp"
                          onChange={(event) => onUploadImage(event.target.files?.[0])}
                        />
                      </label>
                      {post.image_path && (
                        <button className="btn btn-sm btn-danger" type="button" disabled={busy} onClick={onRemoveImage}>
                          <Trash2 size={13} /> Remove image
                        </button>
                      )}
                    </>
                  )}
                  <button className="btn btn-sm" type="button" onClick={onCopy}>
                    {copiedId === `p-${post.id}` ? <Check size={13} /> : <Copy size={13} />}
                    {copiedId === `p-${post.id}` ? "Copied" : "Copy"}
                  </button>
                </div>
                <span className="char-count">{value.length} chars</span>
              </div>

              {post.external_post_url && (
                <a className="post-url" href={post.external_post_url} target="_blank" rel="noreferrer">
                  <ExternalLink /> {post.external_post_url}
                </a>
              )}
              {post.error_message && <p className="note-error">{post.error_message}</p>}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function CommentRow({ comment, isOpen, value, isPublished, busy, copiedId, onToggle, onChange, onSave, onPublish, onCopy }) {
  return (
    <>
      <tr className="post-row" onClick={onToggle}>
        <td>
          <span className="cell-main">{String(value).slice(0, 90) || "Reply draft"}</span>
          <span className="cell-sub">
            {comment.source_post_text ? String(comment.source_post_text).slice(0, 90) : "No source text"}
          </span>
        </td>
        <td>
          <span className={`badge ${statusTone(comment.status)}`}>{prettyStatus(comment.status)}</span>
        </td>
        <td className="nowrap">{relativeTime(comment.created_at)}</td>
        <td className="num">
          <button type="button" className="link-btn" onClick={(event) => { event.stopPropagation(); onToggle(); }}>
            {isOpen ? <ChevronUp /> : <ChevronDown />}
          </button>
        </td>
      </tr>
      {isOpen && (
        <tr className="post-expand">
          <td colSpan={4}>
            <div className="post-editor">
              <textarea value={value} disabled={isPublished} onChange={(event) => onChange(event.target.value)} />
              <div className="post-editor-foot">
                <div className="row" style={{ gap: 6 }}>
                  <button className="btn btn-sm" type="button" disabled={isPublished || busy} onClick={onSave}>
                    Save draft
                  </button>
                  <button
                    className="btn btn-dark btn-sm"
                    type="button"
                    disabled={isPublished || busy}
                    onClick={onPublish}
                  >
                    <Send size={13} /> {isPublished ? "Published" : "Approve & comment"}
                  </button>
                  <button className="btn btn-sm" type="button" onClick={onCopy}>
                    {copiedId === `c-${comment.id}` ? <Check size={13} /> : <Copy size={13} />}
                    {copiedId === `c-${comment.id}` ? "Copied" : "Copy"}
                  </button>
                  {comment.target_url && (
                    <a className="btn btn-sm" href={comment.target_url} target="_blank" rel="noreferrer">
                      <ExternalLink size={13} /> Open post
                    </a>
                  )}
                </div>
                <span className="char-count">{value.length} chars</span>
              </div>
              {comment.error_message && <p className="note-error">{comment.error_message}</p>}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
