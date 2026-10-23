const $ = (selector) => document.querySelector(selector);
const initial = {
  title: "套色入门课",
  email: "studio@example.com",
  description: "三块版，印一张自己的山茶。周六 14:00，版画社二楼，材料都备好了。",
};
let plan = { ...initial };
let persistence = true;
let pending = null;
let timer = null;
try {
  const stored = JSON.parse(localStorage.getItem("qingchun-workshop") || "null");
  if (
    stored &&
    ["title", "email", "description"].every(
      (k) => typeof stored[k] === "string",
    )
  )
    plan = stored;
} catch {
  persistence = false;
}
const states = {
  loading: ["正在载入活动", "版面先留好，内容马上就到。"],
  empty: ["这里还没有活动", "先写下名称和介绍，报名页就能打开。"],
  error: ["活动没能载入", "可能是网络断了一下。已经写好的内容不会丢，点一下重新载入。"],
  offline: ["现在处于离线状态", "这一页还能看；联网后才能保存修改。"],
  denied: ["这场活动只有主办人能改", "需要编辑权限的话，请联系夏禾。"],
};
const requested = new URLSearchParams(location.search).get("state");
if (requested && (requested === "ready" || states[requested]))
  $("#view-state").value = requested;
function render() {
  const state = $("#view-state").value;
  const panel = $("#state-panel");
  // 每次换状态都让内容重新“压印”一次，看得出发生了变化。
  panel.classList.remove("enter");
  void panel.offsetWidth;
  panel.classList.add("enter");
  panel.closest(".event-page")?.setAttribute("data-state", state);
  panel.replaceChildren();
  const title = document.createElement("h3");
  const body = document.createElement("p");
  if (state === "ready") {
    title.textContent = plan.title;
    body.textContent = plan.description;
  } else {
    [title.textContent, body.textContent] = states[state];
  }
  panel.append(title, body);
  if (state === "ready") {
    const when = document.createElement("dl");
    when.className = "event-facts";
    [
      ["时间", "10 月 24 日（周六）14:00–17:00"],
      ["地点", "版画社二楼"],
      ["名额", "还剩 8 个座位"],
      ["费用", "¥180，含纸和颜料"],
    ].forEach(([term, value]) => {
      const row = document.createElement("div");
      const dt = document.createElement("dt");
      const dd = document.createElement("dd");
      dt.textContent = term;
      dd.textContent = value;
      row.append(dt, dd);
      when.append(row);
    });
    panel.append(when);
  }
  if (state === "loading") {
    panel.setAttribute("aria-busy", "true");
    const bars = document.createElement("div");
    bars.className = "skeleton";
    bars.setAttribute("aria-hidden", "true");
    bars.innerHTML = "<span></span><span></span><span></span>";
    panel.append(bars);
  } else panel.removeAttribute("aria-busy");
  if (["error", "offline"].includes(state)) {
    const retry = document.createElement("button");
    retry.textContent = "重新加载";
    retry.onclick = () => {
      $("#view-state").value = "ready";
      render();
    };
    panel.append(retry);
  }
  // 内容没有成功载入时不能基于旧数据编辑：失败时唯一的主动作是重新载入。
  $("#open-dialog").disabled = ["loading", "error", "offline", "denied"].includes(state);
  $("#open-dialog").textContent = state === "empty" ? "创建活动" : "编辑活动";
  $("#persist-status").textContent = persistence
    ? "保存在当前浏览器的本地存储中。"
    : "本地存储不可用，当前更改只保留在页面内存。";
}
$("#view-state").onchange = () => {
  // 换状态后，上一次操作的回执已经过期。
  $("#page-status").textContent = "";
  render();
};
const fields = ["title", "email", "description"];
let draft = null;
const formValues = () =>
  Object.fromEntries(fields.map((key) => [key, $("#" + key).value]));
$("#open-dialog").onclick = () => {
  const empty = $("#view-state").value === "empty";
  const source = draft || (empty ? { title: "", email: "", description: "" } : plan);
  fields.forEach((key) => ($("#" + key).value = source[key]));
  clearFieldErrors();
  $("#form-error").hidden = true;
  $("#save-status").textContent = "";
  $("#draft-note").hidden = !draft;
  $("#editor").showModal();
  $("#title").focus();
};
// 关闭时有改动就留成草稿，下次打开原样恢复，不静默丢掉输入。
function keepDraft() {
  const values = formValues();
  const base = $("#view-state").value === "empty" ? null : plan;
  draft = fields.some((key) => values[key] !== (base?.[key] ?? "")) ? values : null;
}
const messages = {
  title: (input) => (input.validity.valueMissing ? "写一个活动名称，报名页会显示它。" : ""),
  email: (input) =>
    input.validity.valueMissing
      ? "需要一个邮箱，报名的人会联系到这里。"
      : input.validity.typeMismatch
        ? "邮箱格式不对，像 studio@example.com 这样。"
        : "",
};
function clearFieldErrors() {
  Object.keys(messages).forEach((key) => {
    $("#" + key).removeAttribute("aria-invalid");
    $(`#${key}-error`).hidden = true;
  });
}
function checkFields() {
  let first = null;
  Object.entries(messages).forEach(([key, message]) => {
    const input = $("#" + key);
    const text = message(input);
    const error = $(`#${key}-error`);
    error.textContent = text;
    error.hidden = !text;
    if (text) {
      input.setAttribute("aria-invalid", "true");
      first ??= input;
    } else input.removeAttribute("aria-invalid");
  });
  first?.focus();
  return !first;
}
// 只放弃本次草稿，回到已保存的内容；不碰已经保存过的数据。
$("#discard-draft").onclick = () => {
  draft = null;
  const empty = $("#view-state").value === "empty";
  fields.forEach((key) => ($("#" + key).value = empty ? "" : plan[key]));
  clearFieldErrors();
  $("#draft-note").hidden = true;
  $("#save-status").textContent = "已放弃修改，显示的是已保存的内容。";
  $("#title").focus();
};
function cancelPending() {
  pending?.abort();
  pending = null;
  clearTimeout(timer);
  timer = null;
  $("#save").removeAttribute("aria-disabled");
  $("#save").textContent = "保存活动";
}
function close() {
  cancelPending();
  keepDraft();
  $("#editor").close();
}
$("#close-dialog").onclick = close;
$("#cancel").onclick = close;
$("#editor").addEventListener("cancel", () => {
  cancelPending();
  keepDraft();
});
$("#editor").addEventListener("close", () => {
  $("#open-dialog").focus();
});
$("#edit-form").onsubmit = (event) => {
  event.preventDefault();
  const form = event.target;
  $("#title").value = $("#title").value.trim();
  // 保存中按钮只标 aria-disabled，焦点留在按钮上；重复提交在这里拦下。
  if (pending) return;
  if (!checkFields()) return;
  cancelPending();
  const controller = new AbortController();
  pending = controller;
  const next = Object.fromEntries(new FormData(form));
  $("#save").setAttribute("aria-disabled", "true");
  $("#save").textContent = "保存中…";
  $("#save-status").textContent = "正在保存，请稍候。";
  $("#form-error").hidden = true;
  const fail = $("#fail-save").checked;
  timer = setTimeout(() => {
    if (controller.signal.aborted) return;
    pending = null;
    $("#save").removeAttribute("aria-disabled");
    $("#save").textContent = "保存活动";
    if (fail) {
      // 开关只让下一次保存失败，失败后自动关掉，重试即可成功。
      $("#fail-save").checked = false;
      $("#form-error").hidden = false;
      $("#form-error").textContent = "保存失败。输入已保留，请重试。";
      $("#form-error").tabIndex = -1;
      $("#form-error").focus();
      $("#save-status").textContent = "";
      return;
    }
    plan = next;
    draft = null;
    $("#draft-note").hidden = true;
    try {
      localStorage.setItem("qingchun-workshop", JSON.stringify(plan));
      persistence = true;
    } catch {
      persistence = false;
    }
    $("#view-state").value = "ready";
    render();
    $("#editor").close();
    $("#page-status").textContent = persistence
      ? "活动已保存。"
      : "已在页面内更新，浏览器未允许持久保存。";
  }, $("#slow-save").checked ? 3000 : 350);
};
$("#reset").onclick = () => {
  plan = { ...initial };
  draft = null;
  try {
    localStorage.removeItem("qingchun-workshop");
  } catch {
    persistence = false;
  }
  $("#view-state").value = "ready";
  render();
  $("#page-status").textContent = "已恢复初始内容。";
};
window.addEventListener("pagehide", cancelPending);
render();
