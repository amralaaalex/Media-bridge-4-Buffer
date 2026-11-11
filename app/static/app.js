// media-bridge front end: talks to the JSON API in app/main.py. No build step.
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const MAX_BYTES = window.MB.maxUploadMb * 1024 * 1024;
  const TYPES = ["image/jpeg", "image/png", "image/gif", "image/webp"];

  const state = {
    file: null, // the File chosen in the browser
    uploadedId: null, // server id once uploaded; reused if posting fails and is retried
    channels: [],
    files: [],
    pollTimer: null,
  };

  // --- API -------------------------------------------------------------------------

  class ApiError extends Error {
    constructor(status, message) {
      super(message);
      this.status = status;
    }
  }

  async function api(path, options = {}) {
    const res = await fetch(path, { credentials: "same-origin", ...options });
    let body = null;
    try {
      body = await res.json();
    } catch {
      /* empty or non-JSON body */
    }
    if (!res.ok) {
      const detail = body && typeof body.detail === "string" ? body.detail : null;
      if (res.status === 401) {
        throw new ApiError(401, detail || "Your Buffer connection expired. Reconnect to continue.");
      }
      if (res.status === 422 && body && Array.isArray(body.detail)) {
        throw new ApiError(422, "Some fields aren't valid. Check the form and try again.");
      }
      throw new ApiError(res.status, detail || `Something went wrong (${res.status}). Try again.`);
    }
    return body;
  }

  // --- Formatting -----------------------------------------------------------------

  const dateFmt = new Intl.DateTimeFormat(undefined, {
    weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

  function when(iso) {
    return iso ? dateFmt.format(new Date(iso)) : "";
  }

  function relative(iso) {
    if (!iso) return "";
    const diff = (new Date(iso) - Date.now()) / 1000;
    const abs = Math.abs(diff);
    const [value, unit] =
      abs < 60 ? [diff, "second"] :
      abs < 3600 ? [diff / 60, "minute"] :
      abs < 86400 ? [diff / 3600, "hour"] :
      [diff / 86400, "day"];
    return rtf.format(Math.round(value), unit);
  }

  function bytes(n) {
    return n < 1024 * 1024 ? `${Math.round(n / 1024)} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`;
  }

  // What a file's state means for the person, in plain words.
  function describe(f) {
    if (f.state === "UPLOADED") {
      return { tone: "muted", label: "Not posted", detail: `Deleted ${relative(f.expires_at)} unless you post it` };
    }
    if (f.state === "HELD") {
      switch (f.post_status) {
        case "scheduled":
          return f.due_at && new Date(f.due_at) > Date.now()
            ? { tone: "info", label: "Scheduled", detail: `Publishes ${when(f.due_at)}. Image kept until then` }
            : { tone: "live", label: "Publishing", detail: "Due now. Image removed right after it's sent" };
        case "sending":
          return { tone: "live", label: "Publishing", detail: "Buffer is sending it now" };
        case "draft":
          return { tone: "muted", label: "Draft in Buffer", detail: `Image kept while the draft exists, up to ${window.MB.mediaTtlDays} days` };
        case "needs_approval":
          return { tone: "muted", label: "Awaiting approval", detail: "Image kept until it's approved and sent" };
        case "error":
          return { tone: "warn", label: "Buffer couldn't publish", detail: "Image kept so you can retry from Buffer" };
        default:
          return { tone: "info", label: "Waiting", detail: "Image kept until the post is sent" };
      }
    }
    const removed = f.purged_at ? ` ${relative(f.purged_at)}` : "";
    switch (f.removed_reason) {
      case "post_sent":
        return { tone: "ok", label: "Published", detail: `Image deleted${removed}, right after Buffer sent it` };
      case "post_deleted":
        return { tone: "muted", label: "Post deleted in Buffer", detail: `Image deleted${removed}` };
      case "user_deleted":
        return { tone: "muted", label: "Deleted by you", detail: `Image deleted${removed}` };
      case "never_posted":
        return { tone: "muted", label: "Expired", detail: `Never posted, so the image was deleted${removed}` };
      default:
        return { tone: "muted", label: "Removed", detail: `Image deleted${removed}` };
    }
  }

  // --- Toast ----------------------------------------------------------------------

  let toastTimer = null;
  function toast(message) {
    const el = $("toast");
    el.textContent = message;
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.hidden = true; }, 4500);
  }

  // --- File picking ---------------------------------------------------------------

  const dropzone = $("dropzone");
  const fileInput = $("file-input");

  function pickFile(file) {
    showError(null);
    if (!file) return;
    if (!TYPES.includes(file.type)) {
      showError("That file type isn't supported. Use a JPEG, PNG, GIF or WebP image.");
      return;
    }
    if (file.size > MAX_BYTES) {
      showError(`That image is ${bytes(file.size)}. The limit is ${window.MB.maxUploadMb} MB.`);
      return;
    }
    state.file = file;
    state.uploadedId = null; // a new file needs a new upload
    const preview = $("preview");
    if (preview.src) URL.revokeObjectURL(preview.src);
    preview.src = URL.createObjectURL(file);
    preview.alt = file.name;
    $("file-name").textContent = `${file.name} · ${bytes(file.size)}`;
    dropzone.querySelector(".dz-empty").hidden = true;
    dropzone.querySelector(".dz-preview").hidden = false;
  }

  fileInput.addEventListener("change", () => pickFile(fileInput.files[0]));
  // A button inside a <label> doesn't activate the label's input, so open the picker here.
  $("change-file").addEventListener("click", (e) => { e.preventDefault(); fileInput.click(); });
  ["dragenter", "dragover"].forEach((type) =>
    dropzone.addEventListener(type, (e) => { e.preventDefault(); dropzone.classList.add("dragging"); }));
  ["dragleave", "drop"].forEach((type) =>
    dropzone.addEventListener(type, (e) => { e.preventDefault(); dropzone.classList.remove("dragging"); }));
  dropzone.addEventListener("drop", (e) => pickFile(e.dataTransfer.files[0]));
  // Paste an image straight from the clipboard.
  document.addEventListener("paste", (e) => {
    const item = [...(e.clipboardData?.items || [])].find((i) => i.type.startsWith("image/"));
    if (item) pickFile(item.getAsFile());
  });

  // --- Channels -------------------------------------------------------------------

  async function loadChannels() {
    const box = $("channels");
    try {
      state.channels = await api("/api/channels");
    } catch (err) {
      box.innerHTML = "";
      box.append(errorLine(err));
      return;
    }
    box.innerHTML = "";
    if (!state.channels.length) {
      const p = document.createElement("p");
      p.className = "muted";
      p.textContent = "No channels in your Buffer account yet. Connect one in Buffer, then refresh.";
      box.append(p);
      return;
    }
    const firstUsable = state.channels.find((c) => !c.isDisconnected);
    // A Buffer login can belong to several organizations; name them only when it matters.
    const manyOrgs = new Set(state.channels.map((c) => c.organizationId)).size > 1;
    for (const c of state.channels) {
      const label = document.createElement("label");
      label.className = "channel";
      const input = document.createElement("input");
      input.type = "radio";
      input.name = "channel";
      input.value = c.id;
      input.disabled = !!c.isDisconnected;
      input.checked = c === firstUsable;
      const span = document.createElement("span");
      if (c.avatar) {
        const img = document.createElement("img");
        img.src = c.avatar;
        img.alt = "";
        img.referrerPolicy = "no-referrer";
        span.append(img);
      }
      span.append(c.displayName || c.name);
      const small = document.createElement("small");
      small.textContent = c.isDisconnected ? "disconnected" : c.service;
      if (manyOrgs && c.organizationName) small.textContent += ` · ${c.organizationName}`;
      span.append(small);
      label.append(input, span);
      box.append(label);
    }
  }

  function errorLine(err) {
    const p = document.createElement("p");
    p.className = "form-error";
    p.textContent = err.message;
    if (err.status === 401) {
      p.append(" ");
      const a = document.createElement("a");
      a.href = "/login";
      a.textContent = "Reconnect";
      p.append(a);
    }
    return p;
  }

  function channelName(id) {
    const c = state.channels.find((ch) => ch.id === id);
    return c ? `${c.displayName || c.name} · ${c.service}` : "";
  }

  // --- Mode -----------------------------------------------------------------------

  const MODE_COPY = {
    queue: ["Add to queue", "Goes out at the next free slot in this channel's Buffer queue."],
    schedule: ["Schedule post", "Goes out at the time you pick (your local time)."],
    now: ["Publish now", "Buffer sends it straight away."],
    draft: ["Save draft", "Saved as a draft in Buffer. Nothing is published."],
  };

  function currentMode() {
    return document.querySelector('input[name="mode"]:checked').value;
  }

  function defaultDueAt() {
    const d = new Date(Date.now() + 60 * 60 * 1000);
    d.setMinutes(Math.ceil(d.getMinutes() / 15) * 15, 0, 0);
    return toLocalInput(d);
  }

  function toLocalInput(d) {
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  function syncMode() {
    const mode = currentMode();
    const [label, hint] = MODE_COPY[mode];
    $("submit-label").textContent = label;
    $("mode-hint").textContent = hint;
    const row = $("schedule-row");
    row.hidden = mode !== "schedule";
    if (mode === "schedule") {
      const due = $("due-at");
      due.min = toLocalInput(new Date(Date.now() + 5 * 60 * 1000));
      if (!due.value) due.value = defaultDueAt();
    }
  }

  $("modes").addEventListener("change", syncMode);
  $("tz-label").textContent = Intl.DateTimeFormat().resolvedOptions().timeZone || "";

  const text = $("text");
  text.addEventListener("input", () => { $("counter").textContent = text.value.length; });

  // --- Submit ---------------------------------------------------------------------

  function showError(message) {
    const el = $("form-error");
    el.hidden = !message;
    el.textContent = message || "";
  }

  function setBusy(busy, label) {
    const btn = $("submit");
    btn.disabled = busy;
    btn.classList.toggle("busy", busy);
    if (label) $("submit-label").textContent = label;
  }

  $("composer").addEventListener("submit", async (e) => {
    e.preventDefault();
    showError(null);
    const channel = document.querySelector('input[name="channel"]:checked');
    const mode = currentMode();
    if (!state.file) return showError("Choose an image first.");
    if (!channel) return showError("Pick a channel to post to.");

    let dueAt = null;
    if (mode === "schedule") {
      const value = $("due-at").value;
      if (!value) return showError("Pick a date and time.");
      const d = new Date(value); // datetime-local is the browser's local time
      if (d - Date.now() < 60 * 1000) return showError("Pick a time in the future.");
      dueAt = d.toISOString();
    }

    try {
      if (!state.uploadedId) {
        setBusy(true, "Uploading image…");
        const form = new FormData();
        form.append("file", state.file);
        state.uploadedId = (await api("/api/files", { method: "POST", body: form })).id;
      }
      setBusy(true, "Sending to Buffer…");
      const posted = await api(`/api/files/${state.uploadedId}/post`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          channel_id: channel.value,
          text: text.value,
          mode,
          alt_text: $("alt").value.trim() || null,
          due_at: dueAt,
        }),
      });
      toast(successMessage(mode, posted));
      resetComposer();
      await loadFiles();
    } catch (err) {
      showError(err.message);
      if (err.status === 401) $("form-error").append(" ", Object.assign(document.createElement("a"), { href: "/login", textContent: "Reconnect" }));
      if (state.uploadedId) loadFiles(); // the uploaded file now shows as "Not posted"
    } finally {
      setBusy(false);
      syncMode();
    }
  });

  function successMessage(mode, f) {
    if (mode === "draft") return "Saved as a draft in Buffer.";
    if (mode === "now") return "Sent to Buffer to publish now.";
    if (f.due_at) return `Scheduled for ${when(f.due_at)}.`;
    return "Added to your Buffer queue.";
  }

  function resetComposer() {
    state.file = null;
    state.uploadedId = null;
    $("composer").reset();
    fileInput.value = "";
    const preview = $("preview");
    if (preview.src) URL.revokeObjectURL(preview.src);
    preview.removeAttribute("src");
    dropzone.querySelector(".dz-empty").hidden = false;
    dropzone.querySelector(".dz-preview").hidden = true;
    $("counter").textContent = "0";
    $("due-at").value = "";
    const first = document.querySelector('input[name="channel"]:not(:disabled)');
    if (first) first.checked = true;
  }

  // --- File list ------------------------------------------------------------------

  const ICON_GONE = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3"/></svg>';

  const ICON_SENT = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5 10 17l9-10"/></svg>';

  function renderFiles() {
    const list = $("file-list");
    list.innerHTML = "";
    $("files-empty").hidden = state.files.length > 0;
    for (const f of state.files) {
      const info = describe(f);
      const li = document.createElement("li");
      li.className = "file";

      let thumb;
      if (f.url) {
        thumb = document.createElement("img");
        thumb.src = f.url;
        thumb.alt = "";
        thumb.loading = "lazy";
      } else {
        thumb = document.createElement("div");
        thumb.innerHTML = f.post_url ? ICON_SENT : ICON_GONE;
        thumb.title = "Image deleted";
      }
      thumb.className = "thumb";

      const main = document.createElement("div");
      main.className = "file-main";
      // Name the image so the row still means something after the file is deleted.
      const name = document.createElement("p");
      name.className = "file-name";
      name.textContent = f.original_name || "Untitled image"; // rows from before names were kept
      name.title = name.textContent;
      main.append(name);
      const top = document.createElement("div");
      top.className = "file-top";
      const badge = document.createElement("span");
      badge.className = `badge tone-${info.tone}`;
      badge.textContent = info.label;
      top.append(badge);
      const ch = channelName(f.channel_id);
      if (ch) {
        const span = document.createElement("span");
        span.className = "file-channel";
        span.textContent = ch;
        top.append(span);
      }
      const detail = document.createElement("p");
      detail.className = "file-detail";
      detail.textContent = info.detail;
      main.append(top, detail);

      const meta = document.createElement("p");
      meta.className = "file-meta";
      meta.textContent = `Uploaded ${when(f.created_at)}`;
      if (f.post_url) {
        const link = document.createElement("a");
        link.href = f.post_url;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = "View post ↗";
        meta.append(" · ", link);
        // The published post shows the image, so the placeholder links there too.
        const wrap = document.createElement("a");
        wrap.href = f.post_url;
        wrap.target = "_blank";
        wrap.rel = "noopener";
        wrap.title = "Open the published post";
        wrap.className = "thumb-link";
        wrap.append(thumb);
        thumb = wrap;
      }
      main.append(meta);

      li.append(thumb, main);
      if (f.state === "UPLOADED" || f.state === "HELD") {
        const del = document.createElement("button");
        del.type = "button";
        del.className = "link file-delete";
        del.textContent = "Delete now";
        del.addEventListener("click", () => deleteFile(f));
        li.append(del);
      }
      list.append(li);
    }
  }

  async function loadFiles() {
    try {
      state.files = await api("/api/files");
      renderFiles();
    } catch (err) {
      const list = $("file-list");
      list.innerHTML = "";
      list.append(errorLine(err));
    }
    schedulePoll();
  }

  async function deleteFile(f) {
    const pending = f.state === "HELD" && f.post_status !== "sent";
    const question = pending
      ? "This image is still needed by a Buffer post. If you delete it, the post will fail when it publishes. Delete it anyway?"
      : "Delete this image now?";
    if (!confirm(question)) return;
    try {
      const res = await api(`/api/files/${f.id}/delete`, { method: "POST" });
      toast(res.warning ? "Image deleted. Remember to delete or edit the post in Buffer." : "Image deleted.");
    } catch (err) {
      toast(err.message);
    }
    loadFiles();
  }

  // Refresh more often while something is about to change; pause when the tab is hidden.
  function schedulePoll() {
    clearTimeout(state.pollTimer);
    if (document.hidden) return;
    const soon = state.files.some((f) =>
      f.state === "HELD" && (["sending"].includes(f.post_status) ||
        (f.due_at && new Date(f.due_at) - Date.now() < 15 * 60 * 1000)));
    state.pollTimer = setTimeout(loadFiles, soon ? 30 * 1000 : 5 * 60 * 1000);
  }
  document.addEventListener("visibilitychange", () => { if (!document.hidden) loadFiles(); });
  $("refresh").addEventListener("click", loadFiles);

  // --- Account --------------------------------------------------------------------

  $("delete-account").addEventListener("click", async () => {
    if (!confirm("Delete every image and every record media-bridge has about you? Your posts in Buffer are not affected. Posts that still need an image will fail when they publish.")) return;
    try {
      await api("/api/account/delete", { method: "POST" });
      window.location.href = "/";
    } catch (err) {
      toast(err.message);
    }
  });

  // --- Agent access ---------------------------------------------------------------

  const KEY_SLOT = "\u0000KEY\u0000";
  let agentKey = null; // the full key, only in memory and only right after creating it

  function agentPrompt(key) {
    const base = window.MB.baseUrl;
    const local = /^https:\/\/(localhost|127\.0\.0\.1)/.test(base);
    const k = local ? "-k " : "";
    return [
      "You can post images to my Buffer channels through media-bridge, a service built on the Buffer API. It hosts each image until Buffer publishes the post, then deletes it.",
      "",
      "## Connection",
      `Base URL: ${base}`,
      `API key: ${key}`,
      "Send `Authorization: Bearer <API key>` on every request. Keep the key secret: don't print it back to me or write it into files in a repo. Put it in an environment variable named MEDIA_BRIDGE_KEY and use that.",
      ...(local ? ["This is a local server with a self-signed certificate, so add -k to curl."] : []),
      "",
      "## Endpoints",
      "1. List my channels: GET /api/channels -> [{id, name, displayName, service, organizationName}]",
      `2. Upload an image (JPEG, PNG, GIF or WebP, up to ${window.MB.maxUploadMb} MB): POST /api/files as multipart form field "file" -> {id, state: "UPLOADED", ...}`,
      '3. Create the Buffer post for that upload: POST /api/files/{id}/post with JSON {"channel_id", "text", "alt_text", "mode", "due_at"}',
      '   mode is "draft", "queue", "schedule" or "now". due_at is only for "schedule": ISO 8601 with a UTC offset, e.g. "2026-11-20T09:00:00+02:00".',
      "4. Check a file: GET /api/files/{id} -> state (UPLOADED, HELD, PURGED, EXPIRED), post_status, due_at, post_url",
      "5. Delete a file now: POST /api/files/{id}/delete",
      'Errors come back as {"detail": "..."}. Show me that message.',
      "",
      "## Example",
      `curl ${k}-s -H "Authorization: Bearer $MEDIA_BRIDGE_KEY" ${base}/api/channels`,
      `curl ${k}-s -H "Authorization: Bearer $MEDIA_BRIDGE_KEY" -F "file=@./image.png" ${base}/api/files`,
      `curl ${k}-s -H "Authorization: Bearer $MEDIA_BRIDGE_KEY" -H "Content-Type: application/json" -d '{"channel_id":"CHANNEL_ID","text":"Hello","alt_text":"What the image shows","mode":"draft"}' ${base}/api/files/FILE_ID/post`,
      "",
      "## Rules",
      '- "now", "queue" and "schedule" publish publicly. Confirm the channel, text and time with me before using them. Use "draft" when unsure.',
      "- Always write alt text that describes the image.",
      "- One post per uploaded file.",
      "- After a post is published, media-bridge deletes its image automatically. You don't need to clean up.",
      "",
      "To confirm you're connected, list my channels and tell me their names.",
    ].join("\n");
  }

  function renderPrompt() {
    const pre = $("agent-prompt");
    pre.textContent = "";
    const [before, after] = agentPrompt(KEY_SLOT).split(KEY_SLOT);
    pre.append(before);
    if (agentKey) {
      pre.append(agentKey);
    } else {
      const slot = document.createElement("span");
      slot.className = "placeholder";
      slot.textContent = "<click Create agent key>";
      pre.append(slot);
    }
    pre.append(after);
    $("copy-prompt").disabled = !agentKey;
  }

  $("create-key").addEventListener("click", async () => {
    const btn = $("create-key");
    btn.disabled = true;
    btn.classList.add("busy");
    try {
      const created = await api("/api/agent-keys", { method: "POST" });
      agentKey = created.key;
      renderPrompt();
      $("key-note").textContent =
        "Your new key is in the prompt above. It won't be shown again, so copy the prompt now. Anyone with the key can post to your Buffer channels through media-bridge; revoke it below if it leaks.";
      toast("Agent key created. Copy the prompt now; the key won't be shown again.");
      loadKeys();
    } catch (err) {
      toast(err.message);
    } finally {
      btn.disabled = false;
      btn.classList.remove("busy");
    }
  });

  $("copy-prompt").addEventListener("click", async () => {
    if (!agentKey) return;
    const text = agentPrompt(agentKey);
    try {
      await navigator.clipboard.writeText(text);
      toast("Prompt copied. Paste it into your agent's chat.");
    } catch {
      // Clipboard API blocked: select the text so Ctrl/Cmd+C works.
      const range = document.createRange();
      range.selectNodeContents($("agent-prompt"));
      const sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
      toast("Press Ctrl+C (or Cmd+C) to copy the selected prompt.");
    }
  });

  async function loadKeys() {
    let keys = [];
    try {
      keys = await api("/api/agent-keys");
    } catch {
      return;
    }
    $("keys-section").hidden = keys.length === 0;
    const list = $("key-list");
    list.innerHTML = "";
    for (const k of keys) {
      const li = document.createElement("li");
      const code = document.createElement("code");
      code.textContent = `${k.prefix}…`;
      const info = document.createElement("span");
      info.className = "muted";
      info.textContent = `Created ${when(k.created_at)} · ${k.last_used_at ? `last used ${relative(k.last_used_at)}` : "not used yet"}`;
      const revoke = document.createElement("button");
      revoke.type = "button";
      revoke.className = "link";
      revoke.textContent = "Revoke";
      revoke.addEventListener("click", async () => {
        if (!confirm(`Revoke key ${k.prefix}…? Agents using it will stop working immediately.`)) return;
        try {
          await api(`/api/agent-keys/${k.id}/revoke`, { method: "POST" });
          toast("Key revoked.");
        } catch (err) {
          toast(err.message);
        }
        loadKeys();
      });
      li.append(code, info, revoke);
      list.append(li);
    }
  }

  // --- Start ----------------------------------------------------------------------

  syncMode();
  loadChannels().then(renderFiles); // channel names appear in the file list
  loadFiles();
  renderPrompt();
  loadKeys();
})();
