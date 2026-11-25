async function request(path, options = {}) {
  const resp = await fetch(`/api${path}`, {
    headers: options.body instanceof FormData ? {} : { "Content-Type": "application/json" },
    ...options,
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(data.detail || data.message || `HTTP ${resp.status}`);
  }
  return data;
}

export const api = {
  getProfile: () => request("/profile"),
  updateProfile: (payload) => request("/profile", { method: "PUT", body: JSON.stringify(payload) }),
  uploadCv: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/profile/upload-cv", { method: "POST", body: form });
  },
  uploadCvWithProgress: (file, onProgress) =>
    new Promise((resolve, reject) => {
      const form = new FormData();
      form.append("file", file);
      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/api/profile/upload-cv");
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          onProgress?.(Math.round((event.loaded / event.total) * 100));
        }
      };
      xhr.onload = () => {
        let data = {};
        try {
          data = JSON.parse(xhr.responseText);
        } catch {
          data = {};
        }
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(data);
        } else {
          reject(new Error(data.detail || data.message || `HTTP ${xhr.status}`));
        }
      };
      xhr.onerror = () => reject(new Error("Upload failed. Check that the backend is running."));
      xhr.send(form);
    }),
  reextractCv: () => request("/profile/re-extract", { method: "POST" }),
  importLinkedIn: (profile_text = "") =>
    request("/profile/import-linkedin", { method: "POST", body: JSON.stringify({ profile_text }) }),
  reviewProfile: () => request("/profile/review", { method: "POST" }),
  getNotes: () => request("/profile/notes"),
  createNote: (payload) => request("/profile/notes", { method: "POST", body: JSON.stringify(payload) }),
  deleteNote: (id) => request(`/profile/notes/${id}`, { method: "DELETE" }),

  getAutopilot: () => request("/autopilot"),
  updateAutopilot: (payload) =>
    request("/autopilot", { method: "PUT", body: JSON.stringify(payload) }),
  queueAutopilot: (limit = 1) => request(`/autopilot/queue?limit=${limit}`, { method: "POST" }),

  getPosts: () => request("/content/posts"),
  generatePost: (payload) => request("/content/posts/generate", { method: "POST", body: JSON.stringify(payload) }),
  updatePost: (id, payload) => request(`/content/posts/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  publishPost: (id) => request(`/content/posts/${id}/publish`, { method: "POST" }),
  generatePostImage: (id, custom_prompt = "") =>
    request(`/content/posts/${id}/generate-image`, { method: "POST", body: JSON.stringify({ custom_prompt }) }),
  uploadPostImage: (id, file) => {
    const form = new FormData();
    form.append("file", file);
    return request(`/content/posts/${id}/upload-image`, { method: "POST", body: form });
  },
  removePostImage: (id) => request(`/content/posts/${id}/image`, { method: "DELETE" }),

  getComments: () => request("/content/comments"),
  generateComment: (payload) => request("/content/comments/generate", { method: "POST", body: JSON.stringify(payload) }),
  updateComment: (id, draft_reply) =>
    request(`/content/comments/${id}`, { method: "PUT", body: JSON.stringify({ draft_reply }) }),
  publishComment: (id) => request(`/content/comments/${id}/publish`, { method: "POST" }),
  replyCommentNow: (payload) =>
    request("/content/comments/reply-now", { method: "POST", body: JSON.stringify(payload) }),

  getJobs: () => request("/jobs"),
  discoverJobs: ({ q = "", location = "", limit = 80, refresh = false } = {}) => {
    const params = new URLSearchParams({
      q,
      location,
      limit: String(limit),
      refresh: refresh ? "true" : "false",
    });
    return request(`/jobs/discover?${params.toString()}`);
  },
  trackJob: (payload) => request("/jobs/track", { method: "POST", body: JSON.stringify(payload) }),
  importJob: (payload) => request("/jobs/import", { method: "POST", body: JSON.stringify(payload) }),
  prepareJob: (id) => request(`/jobs/${id}/prepare`, { method: "POST" }),
  updateJobStatus: (id, status) =>
    request(`/jobs/${id}/status`, { method: "PUT", body: JSON.stringify({ status }) }),

  getConnectors: () => request("/connectors"),
  connectPlatform: (platform) => request(`/connectors/${platform}/connect`),
  disconnectPlatform: (platform) => request(`/connectors/${platform}/disconnect`, { method: "POST" }),

  getChatHistory: () => request("/chat/history"),
  sendChat: (message) => request("/chat", { method: "POST", body: JSON.stringify({ message }) }),

  getSettings: () => request("/settings"),
  updateSettings: (payload) => request("/settings", { method: "PUT", body: JSON.stringify(payload) }),
};
