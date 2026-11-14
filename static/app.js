// Ratatoskr Web. Names and messages are inserted with textContent only.
"use strict";

const form = $("#form");
let recipients = [];
let limits = { total: 20, length: 4000 };
let timer = null;

function drawRecipients() {
  const box = $("#recipients");
  box.querySelectorAll(".tag").forEach((n) => n.remove());
  for (const name of recipients) {
    box.insertBefore(el("span", { class: "tag" }, name,
      el("button", { type: "button", "aria-label": `Remove ${name}`, onclick: () => { recipients = recipients.filter((x) => x !== name); drawRecipients(); } }, "×")), $("#contact"));
  }
  preview();
}
function addRecipient(name) {
  name = name.trim();
  if (name && !recipients.includes(name) && recipients.length < 20) recipients.push(name);
  drawRecipients();
}
$("#contact").addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === ",") {
    event.preventDefault();
    addRecipient(event.target.value);
    event.target.value = "";
  } else if (event.key === "Backspace" && !event.target.value && recipients.length) {
    recipients.pop();
    drawRecipients();
  }
});
$("#recipients").addEventListener("click", () => $("#contact").focus());

function preview() {
  const f = new FormData(form);
  const text = f.get("text").trim();
  const repeat = Math.max(1, Number(f.get("repeat")) || 1);
  const total = recipients.length * repeat;
  const name = recipients[0] || "Recipient";
  $("#chat-name").textContent = recipients.length > 1 ? `${name} +${recipients.length - 1}` : name;
  $("#avatar").textContent = name.slice(0, 1).toUpperCase();
  const at = f.get("at").trim();
  const time = /^\d{1,2}:\d{2}$/.test(at) ? at.padStart(5, "0") : new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const bubbles = text ? Array.from({ length: Math.min(repeat, 4) }, () =>
    el("div", { class: "bubble" }, el("span", { class: "bubble__text" }, text), el("span", { class: "bubble__time" }, `${time} ✓✓`))) : [];
  if (repeat > 4) bubbles.push(el("p", { class: "phone__more" }, `+${repeat - 4} more`));
  $("#bubbles").replaceChildren(...(bubbles.length ? bubbles : [el("p", { class: "phone__hint" }, "Your message appears here.")]));
  const over = total > limits.total;
  $("#count").textContent = `${text.length} / ${limits.length} characters · ${total} message${total === 1 ? "" : "s"} in this job${over ? ` (limit ${limits.total})` : ""}`;
  $("#count").classList.toggle("bad", over || text.length > limits.length);
  const dry = form.elements.dry_run.checked;
  $("#go").textContent = dry ? "Try it (dry run)" : at ? `Schedule for ${time}` : "Send now";
  $("#go").classList.toggle("btn--danger", !dry);
}
form.addEventListener("input", preview);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if ($("#contact").value.trim()) { addRecipient($("#contact").value); $("#contact").value = ""; }
  const f = new FormData(form);
  showError("");
  const body = { contacts: recipients, text: f.get("text"), repeat: Number(f.get("repeat")), delay: Number(f.get("delay")),
    at: f.get("at").trim(), dry_run: f.has("dry_run") };
  if (!body.dry_run && !confirm(`Send ${recipients.length * body.repeat} WhatsApp message(s) to ${recipients.join(", ")}?`)) return;
  try {
    render(await api("/api/jobs", body));
    toast(body.dry_run ? "Dry run started" : body.at ? `Scheduled for ${body.at}` : "Sending…");
  } catch (error) { showError(error.message); }
});
function showError(text) { const e = $("#error"); e.textContent = text; e.hidden = !text; }

const STATE = { queued: ["waiting", ""], scheduled: ["scheduled", "badge--accent"], running: ["sending", "badge--warn"],
  sent: ["sent", "badge--good"], "dry-run": ["dry run ok", "badge--good"], failed: ["failed", "badge--bad"], cancelled: ["cancelled", ""] };

function render(s) {
  limits = s.limits;
  $("#version").textContent = `v${s.version}`;
  $("#recent").replaceChildren(...s.recent.map((name) =>
    el("button", { type: "button", class: "chip-btn", onclick: () => addRecipient(name) }, `+ ${name}`)));
  const list = $("#jobs");
  if (!s.jobs.length) {
    list.replaceChildren(el("div", { class: "empty" }, el("p", {}, "No jobs yet."), el("p", { class: "muted" }, "Dry runs are a safe way to start.")));
  } else {
    list.replaceChildren(...s.jobs.map(job));
  }
  clearTimeout(timer);
  if (s.jobs.some((j) => ["queued", "scheduled", "running"].includes(j.state))) timer = setTimeout(load, 1000);
  preview();
}

function job(j) {
  const [label, cls] = STATE[j.state] || [j.state, ""];
  const when = j.send_at ? `at ${new Date(j.send_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : new Date(j.created).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return el("article", { class: "job" },
    el("div", { class: "job__head" },
      el("span", { class: `badge ${cls}` }, label),
      el("span", { class: "job__to" }, j.contacts.join(", ")),
      el("span", { class: "note mono" }, `${j.repeat}× · ${when}`)),
    el("p", { class: "job__text" }, j.text),
    j.log.length ? el("pre", { class: "job__log" }, j.log.join("\n")) : null,
    j.state === "scheduled" || j.state === "queued"
      ? el("button", { type: "button", class: "btn btn--small btn--ghost", onclick: () => cancel(j.id) }, "Cancel") : null);
}

async function cancel(id) {
  try { render(await api(`/api/jobs/${id}/cancel`, {})); } catch (error) { toast(error.message); }
}
async function load() {
  try { render(await api("/api/state")); } catch (error) { showError(error.message); }
}
load();
