function parseDate(value) {
  if (!value) return null;
  let raw = String(value).trim();
  if (!raw) return null;
  if (/^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}/.test(raw) && !/(z|[+-]\d{2}:?\d{2})$/i.test(raw)) {
    raw = `${raw.replace(" ", "T")}Z`;
  } else if (raw.includes(" ") && !raw.includes("T")) {
    raw = raw.replace(" ", "T");
  }
  const date = new Date(raw);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function initials(name) {
  const parts = String(name || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (!parts.length) return "YO";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

export function firstName(name) {
  const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
  return parts[0] || "there";
}

export function relativeTime(value) {
  const date = parseDate(value);
  if (!date) return "—";
  const diff = Date.now() - date.getTime();
  if (diff < 45 * 1000) return "just now";
  const minutes = Math.floor(diff / 60000);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function formatDate(value) {
  const date = parseDate(value);
  if (!date) return "—";
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export function dayKey(value) {
  const date = parseDate(value);
  if (!date) return "";
  return date.toISOString().slice(0, 10);
}

export function localDayKey(value) {
  const date = parseDate(value);
  if (!date) return "";
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export function scoreTone(score) {
  if (score >= 75) return "ok";
  if (score >= 50) return "info";
  return "warn";
}

export function statusTone(status) {
  switch (String(status || "").toLowerCase()) {
    case "published":
    case "offer":
      return "ok";
    case "scheduled":
    case "preparing":
    case "interview":
      return "info";
    case "draft":
    case "saved":
      return "neutral";
    case "manual_required":
      return "warn";
    case "applied":
      return "info";
    case "failed":
    case "rejected":
      return "err";
    default:
      return "neutral";
  }
}

export function prettyStatus(status) {
  if (!status) return "Unknown";
  return String(status)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}
