#!/usr/bin/env node
// weicoz-herdr-hub：管理全部 Herdr 窗口、派单、20 分钟汇报。
// 状态目录可用 WEICOZ_HERDR_HUB_STATE_DIR 覆盖；不写死任何用户绝对路径。
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const HOME = os.homedir();
const STATE_DIR = process.env.WEICOZ_HERDR_HUB_STATE_DIR || path.join(HOME, ".local", "state", "weicoz-herdr-hub");
const REPORT_DIR = path.join(STATE_DIR, "reports");
const TASK_DIR = path.join(STATE_DIR, "tasks");
const REGISTRY_FILE = path.join(STATE_DIR, "registry.json");
const SNAPSHOT_FILE = path.join(STATE_DIR, "snapshot.json");
const PID_FILE = path.join(STATE_DIR, "watch.pid");
const OWNER = process.env.WEICOZ_HERDR_HUB_OWNER || process.env.HERDR_PANE_ID || "unknown-owner";
const NOTIFY_HARNESS = process.env.WEICOZ_HERDR_HUB_NOTIFY_HARNESS || "dsh";
const STALL_MS = Number(process.env.WEICOZ_HERDR_HUB_STALL_MINUTES || 40) * 60 * 1000;
const STATUSES = ["待发", "已发", "进行中", "待验收", "已验收", "已打回", "受阻", "已取消"];

function say(msg) { process.stdout.write(msg + "\n"); }
function die(code, msg) { process.stderr.write(msg.replace(/\n?$/, "\n")); process.exit(code); }
function nowIso() { return new Date().toISOString(); }
function pad(n) { return String(n).padStart(2, "0"); }
function stamp(d) {
  const t = d || new Date();
  return t.getFullYear() + "-" + pad(t.getMonth() + 1) + "-" + pad(t.getDate()) + " " + pad(t.getHours()) + ":" + pad(t.getMinutes());
}
function minutesAgo(iso) {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  if (!isFinite(diff)) return "";
  if (diff < 60000) return "不到 1 分钟前";
  return Math.round(diff / 60000) + " 分钟前";
}

// ---------- herdr 调用 ----------
function herdrRaw(args, opts) {
  const timeout = (opts && opts.timeout) || 60000;
  const r = spawnSync("herdr", args, { encoding: "utf8", timeout: timeout, maxBuffer: 64 * 1024 * 1024 });
  if (r.error) die(1, "无法运行 herdr：" + r.error.message + "。先确认 herdr 已安装、PATH 正确，并在 Herdr 环境内执行。");
  return { status: r.status, stdout: (r.stdout || "").trim(), stderr: (r.stderr || "").trim() };
}
function herdrJson(args) {
  const r = herdrRaw(args);
  const text = r.stdout || r.stderr;
  try { return JSON.parse(text); } catch (e) {
    die(1, "herdr " + args.join(" ") + " 未返回 JSON（退出码 " + r.status + "）：" + text.slice(0, 300));
  }
}
function progressKey(p) {
  return p.pane_id + "@" + p.revision + ":" + p.agent_status + ":" + p.state_change_seq;
}
// herdr 在代理刚结束一轮时会短暂报告 done 等收尾状态，这些都要按空闲处理。
const IDLE_STATUSES = ["idle", "done", "ready", "finished", "waiting"];
function isIdleStatus(s) { return IDLE_STATUSES.indexOf(s) >= 0; }
function readLive() {
  const res = herdrJson(["api", "snapshot"]);
  const snap = res && res.result && res.result.snapshot;
  if (!snap) die(1, "herdr api snapshot 缺少 result.snapshot，可能是版本不兼容。");
  const label = {};
  (snap.workspaces || []).forEach(function (w) { label[w.workspace_id] = w.label || w.workspace_id; });
  const seq = {};
  (snap.agents || []).forEach(function (a) { if (a.pane_id) seq[a.pane_id] = a; });
  const panes = (snap.panes || []).map(function (p) {
    const a = seq[p.pane_id] || {};
    return {
      pane_id: p.pane_id,
      workspace_id: p.workspace_id,
      workspace: label[p.workspace_id] || p.workspace_id,
      agent: p.agent || "",
      agent_status: p.agent_status || "unknown",
      cwd: p.cwd || "",
      foreground_cwd: p.foreground_cwd || p.cwd || "",
      title: p.terminal_title_stripped || p.terminal_title || "",
      revision: typeof p.revision === "number" ? p.revision : -1,
      state_change_seq: typeof a.state_change_seq === "number" ? a.state_change_seq : -1,
      completion_seq: typeof a.completion_seq === "number" ? a.completion_seq : -1,
      focused: !!p.focused
    };
  });
  return { taken_at: nowIso(), protocol: snap.protocol || "", version: snap.version || "", panes: panes };
}
function readPrevSnapshot() {
  if (!fs.existsSync(SNAPSHOT_FILE)) return null;
  try { return JSON.parse(fs.readFileSync(SNAPSHOT_FILE, "utf8")); } catch (e) { return null; }
}
function writeSnapshot(live) {
  fs.mkdirSync(STATE_DIR, { recursive: true });
  fs.writeFileSync(SNAPSHOT_FILE, JSON.stringify(live, null, 2));
}
function paneReadTail(paneId, lines) {
  const r = herdrRaw(["pane", "read", paneId, "--source", "recent-unwrapped", "--lines", String(lines || 40)]);
  return (r.stdout || "").split("\n").map(function (s) { return s.trim(); }).filter(Boolean);
}
// 终端界面自带边框、输入行、状态栏；摘录只留真正的输出内容。
function isChromeLine(s) {
  if (!s) return true;
  if (!/[0-9A-Za-z\u4e00-\u9fff]/.test(s)) return true;
  if (/^[─━═│┃╌╍┄┅┈┉·•\-=_|]{3,}/.test(s)) return true;
  return /(Ctx:|Cache:|bypass permissions|press .{0,8} to cycle|Esc to interrupt|✻ Brewed|Update installed|\bOpus\b|\bSonnet\b|\bHaiku\b|→ \d+ agents?)/.test(s);
}
function excerptTail(paneId) {
  const kept = paneReadTail(paneId, 40).filter(function (s) { return !isChromeLine(s); });
  return kept.slice(-3).join(" / ").slice(0, 300);
}

// ---------- 台账 ----------
function loadRegistry() {
  if (!fs.existsSync(REGISTRY_FILE)) return { version: 1, lines: [] };
  try {
    const reg = JSON.parse(fs.readFileSync(REGISTRY_FILE, "utf8"));
    if (!reg || !Array.isArray(reg.lines)) return { version: 1, lines: [] };
    return reg;
  } catch (e) { return { version: 1, lines: [] }; }
}
function saveRegistry(reg) {
  fs.mkdirSync(STATE_DIR, { recursive: true });
  fs.writeFileSync(REGISTRY_FILE, JSON.stringify(reg, null, 2));
}
function newId() { return "L" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }
function pushEvent(line, kind, note) {
  line.events = line.events || [];
  line.events.push({ at: nowIso(), kind: kind, note: note || "" });
  if (line.events.length > 20) line.events = line.events.slice(line.events.length - 20);
}
function findLine(reg, id) {
  if (!id) return null;
  const exact = reg.lines.find(function (l) { return l.id === id; });
  if (exact) return exact;
  const matches = reg.lines.filter(function (l) { return l.id.startsWith(id); });
  if (matches.length === 1) return matches[0];
  if (matches.length > 1) die(2, "id " + id + " 匹配到多条工作线，请写完整 id。");
  return null;
}

// ---------- 参数 ----------
function parseArgs(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--") { out._ = out._.concat(argv.slice(i + 1)); break; }
    if (a.indexOf("--") === 0) {
      const key = a.slice(2);
      const next = argv[i + 1];
      if (next === undefined || next.indexOf("--") === 0) out[key] = true;
      else { out[key] = next; i++; }
    } else out._.push(a);
  }
  return out;
}
function flag(args, key) {
  const v = args[key];
  if (typeof v !== "string" || !v.trim()) return null;
  return v.trim();
}

// ---------- 指令 ----------
function cmdInit() {
  [STATE_DIR, REPORT_DIR, TASK_DIR].forEach(function (d) { fs.mkdirSync(d, { recursive: true }); });
  say("状态目录已就绪：" + STATE_DIR);
  say("报告目录：" + REPORT_DIR);
  say("派单文件目录：" + TASK_DIR);
  say("当前总控：" + OWNER + "（取自 HERDR_PANE_ID，可用 WEICOZ_HERDR_HUB_OWNER 覆盖）");
  return 0;
}

function diffPanes(prev, live) {
  const old = {};
  ((prev && prev.panes) || []).forEach(function (p) { old[p.pane_id] = p; });
  const changed = [];
  const added = [];
  live.panes.forEach(function (p) {
    const before = old[p.pane_id];
    if (!before) { added.push(p); return; }
    if (before.revision !== p.revision || before.agent_status !== p.agent_status || before.state_change_seq !== p.state_change_seq) {
      changed.push({ pane: p, before: before });
    }
  });
  const gone = Object.keys(old).filter(function (id) { return !live.panes.some(function (p) { return p.pane_id === id; }); }).map(function (id) { return old[id]; });
  return { changed: changed, added: added, gone: gone };
}

function cmdSnapshot(args) {
  const live = readLive();
  const prev = readPrevSnapshot();
  const d = diffPanes(prev, live);
  writeSnapshot(live);
  const reg = loadRegistry();
  const managed = {};
  reg.lines.forEach(function (l) { if (l.target_pane) managed[l.target_pane] = l; });
  if (args.json) {
    say(JSON.stringify({
      taken_at: live.taken_at,
      panes: live.panes,
      changed: d.changed.map(function (c) { return c.pane.pane_id; }),
      added: d.added.map(function (p) { return p.pane_id; }),
      gone: d.gone.map(function (p) { return p.pane_id; })
    }, null, 2));
    return 0;
  }
  const ws = {};
  live.panes.forEach(function (p) {
    ws[p.workspace] = ws[p.workspace] || { panes: 0, working: 0, idle: 0, blocked: 0, other: 0 };
    ws[p.workspace].panes++;
    const k = isIdleStatus(p.agent_status) ? "idle" : (["working", "blocked"].indexOf(p.agent_status) >= 0 ? p.agent_status : "other");
    ws[p.workspace][k]++;
  });
  say("Herdr 快照 " + stamp());
  say("共 " + Object.keys(ws).length + " 个工作区 / " + live.panes.length + " 个 pane / " + live.panes.filter(function (p) { return p.agent; }).length + " 个代理；受管 " + reg.lines.filter(function (l) { return l.status !== "已取消"; }).length + " 条。");
  Object.keys(ws).forEach(function (name) {
    const w = ws[name];
    say("  " + name + "：" + w.panes + " pane（working " + w.working + " / idle " + w.idle + " / blocked " + w.blocked + " / 其它 " + w.other + "）");
  });
  if (prev) {
    say("变化：" + d.changed.length + " 个 pane 有更新" + (d.added.length ? "，新增 " + d.added.length : "") + (d.gone.length ? "，消失 " + d.gone.length : "") + "。");
    d.changed.slice(0, 12).forEach(function (c) {
      const p = c.pane;
      say("  " + p.pane_id + " " + (p.agent || "shell") + " " + p.agent_status + "  rev " + c.before.revision + "→" + p.revision + "  " + p.workspace + "  " + (managed[p.pane_id] ? "[受管] " + managed[p.pane_id].title : p.title));
    });
  } else {
    say("首次快照，已保存基线；下次运行即可对比变化。");
  }
  return 0;
}

function resolveDir(p) {
  const abs = path.resolve(p);
  try { return fs.realpathSync(abs); } catch (e) { return abs; }
}

function pickTarget(args, live) {
  const paneId = flag(args, "pane");
  const project = flag(args, "project");
  if (paneId) {
    const pane = live.panes.find(function (p) { return p.pane_id === paneId; });
    if (!pane) die(1, "没有找到 pane " + paneId + "。先运行 hub.mjs snapshot 核对。");
    if (project) {
      const want = resolveDir(project);
      const got = resolveDir(pane.foreground_cwd || pane.cwd);
      if (got !== want) {
        die(3, [
          "拒绝派单：目标 pane 的目录与项目不符。",
          "  pane " + paneId + " 当前在 " + got,
          "  你要派往 " + want,
          "我不改别人的窗口目录。请选一个：",
          "  1. 在该项目目录新开 pane 再派：--project " + want + " --new",
          "  2. 指定另一个 pane：换 --pane",
          "  3. 明确要求我改这个 pane 的目录，并说明原因（我不默认做）"
        ].join("\n"));
      }
    }
    return { pane: pane, project: project ? resolveDir(project) : resolveDir(pane.foreground_cwd || pane.cwd) };
  }
  if (!project) {
    die(2, [
      "需要先确定派给哪个项目/目录，我不猜。",
      "请给其中一项：",
      "  --project <目录> --new            在该目录新开 pane",
      "  --project <目录>                  复用该目录下空闲的受管 pane",
      "  --pane <pane_id> --project <目录>  指定已有窗口（目录必须一致）",
      "可用 hub.mjs ls 或 hub.mjs snapshot 看现有窗口。"
    ].join("\n"));
  }
  const want = resolveDir(project);
  const idle = live.panes.filter(function (p) {
    return resolveDir(p.foreground_cwd || p.cwd) === want && p.agent && isIdleStatus(p.agent_status);
  });
  if (idle.length) return { pane: idle[0], project: want };
  if (args.new) {
    if (!process.env.HERDR_PANE_ID) die(1, "--new 需要在 Herdr pane 内执行（HERDR_PANE_ID 未设置）。");
    const dir = args.direction === "down" ? "down" : "right";
    const res = herdrJson(["pane", "split", "--current", "--direction", dir, "--cwd", want, "--no-focus"]);
    const newPaneId = res && res.result && res.result.pane && res.result.pane.pane_id;
    if (!newPaneId) die(1, "pane split 未返回 pane_id：" + JSON.stringify(res).slice(0, 300));
    const refreshed = readLive().panes.find(function (p) { return p.pane_id === newPaneId; });
    say("已新开 pane " + newPaneId + "（cwd " + want + "）。");
    return {
      pane: refreshed || { pane_id: newPaneId, agent: "", agent_status: "unknown", foreground_cwd: want, workspace: "", title: "" },
      project: want,
      fresh: true
    };
  }
  die(2, [
    "目录 " + want + " 下没有空闲的可复用 pane。",
    "请选一个：",
    "  --new                       在该目录新开 pane（我会用 pane split）",
    "  --pane <pane_id>             指定别处的窗口（目录不同我会拒绝）",
    "  --force-send                 仍然派给该目录下正在忙的 pane（排队，不打断）"
  ].join("\n"));
}

function writeTaskFile(line, prompt, project) {
  fs.mkdirSync(TASK_DIR, { recursive: true });
  const file = path.join(TASK_DIR, line.id + ".md");
  const body = [
    "# " + line.title,
    "",
    "- 工作线 id：" + line.id,
    "- 项目目录：" + project,
    "- 总控 pane：" + line.dispatcher_pane,
    "- 派发时间：" + line.created_at,
    "",
    "## 任务",
    "",
    prompt.trim(),
    "",
    "## 完成判据",
    "",
    line.criteria || "（未写，需先补）",
    "",
    "## 权限边界",
    "",
    "只改本任务范围内的文件。提交、推送、部署、对外发送须用户授权。",
    "",
    "## 汇报要求",
    "",
    "结束时以 [汇报] 开头，写出：状态、改动文件、验证命令与结果、未完成项。",
    ""
  ].join("\n");
  fs.writeFileSync(file, body);
  return file;
}

function sendToPane(paneId, text) {
  // herdr pane run 成功时返回纯文本，不是 JSON：只按退出码判定。
  const res = herdrRaw(["pane", "run", paneId, text]);
  if (res.status !== 0) die(1, "派单失败（herdr 退出码 " + res.status + "）：" + (res.stderr || res.stdout).slice(0, 300));
  return true;
}

function cmdDispatch(args) {
  const title = flag(args, "title");
  const criteria = flag(args, "criteria");
  let prompt = flag(args, "prompt");
  const promptFile = flag(args, "prompt-file");
  if (promptFile) {
    if (!fs.existsSync(promptFile)) die(1, "找不到派单文件：" + promptFile);
    prompt = fs.readFileSync(promptFile, "utf8");
  }
  const missing = [];
  if (!title) missing.push("--title 工作线名称（例：billing-api 加取消接口）");
  if (!prompt) missing.push("--prompt 任务说明 或 --prompt-file 文件路径");
  if (!criteria) missing.push("--criteria 可验证的完成判据（文件、命令、页面，不能写做完）");
  if (missing.length) {
    die(2, ["派单信息不完整，先补齐（我不替你猜）："].concat(missing.map(function (m) { return "  " + m; })).join("\n"));
  }
  const live = readLive();
  const target = pickTarget(args, live);
  const pane = target.pane;
  const reg = loadRegistry();
  const line = {
    id: newId(),
    owner_session: OWNER,
    parent_id: flag(args, "parent") || null,
    dispatcher_pane: OWNER,
    target_pane: pane.pane_id,
    project_dir: target.project,
    title: title,
    status: "待发",
    criteria: criteria,
    prompt_file: null,
    created_at: nowIso(),
    sent_at: null,
    last_progress_key: null,
    last_change_at: null,
    verdict: null,
    decided_at: null,
    notes: "",
    events: []
  };
  const isLong = prompt.length > 200 || prompt.indexOf("\n") >= 0;
  if (isLong) line.prompt_file = writeTaskFile(line, prompt, target.project);
  const busy = pane.agent_status === "working" || pane.agent_status === "blocked";
  if (busy && !args["force-send"]) {
    line.status = "待发";
    line.notes = "目标 pane 正忙（" + pane.agent_status + "），已排队；空闲后用 hub.mjs flush 发出。";
    pushEvent(line, "排队", line.notes);
    reg.lines.push(line);
    saveRegistry(reg);
    say("已登记并排队：" + line.id + " → " + pane.pane_id + "（" + pane.agent_status + "）。");
    say("目标空闲后运行：hub.mjs flush");
    return 0;
  }
  const text = line.prompt_file
    ? "读取 " + line.prompt_file + " 并按其执行。结束时以 [汇报] 开头写结论。"
    : prompt;
  sendToPane(pane.pane_id, text);
  line.status = "已发";
  line.sent_at = nowIso();
  pushEvent(line, "已发", "发往 " + pane.pane_id);
  reg.lines.push(line);
  saveRegistry(reg);
  say("已派单 " + line.id);
  say("  工作线：" + title);
  say("  目标：  " + pane.pane_id + "（" + (pane.agent || "shell") + "，" + pane.agent_status + "）");
  say("  项目：  " + target.project);
  if (line.prompt_file) say("  任务文件：" + line.prompt_file);
  return 0;
}

function cmdFlush(args) {
  const live = readLive();
  const reg = loadRegistry();
  let sent = 0;
  reg.lines.forEach(function (line) {
    if (line.status !== "待发") return;
    const pane = live.panes.find(function (p) { return p.pane_id === line.target_pane; });
    if (!pane) return;
    if (!isIdleStatus(pane.agent_status) && !args["force-send"]) return;
    const text = line.prompt_file
      ? "读取 " + line.prompt_file + " 并按其执行。结束时以 [汇报] 开头写结论。"
      : "按此前登记的派单执行，结束时以 [汇报] 开头写结论。";
    sendToPane(pane.pane_id, text);
    line.status = "已发";
    line.sent_at = nowIso();
    line.notes = "";
    pushEvent(line, "已发", "排队后补发到 " + pane.pane_id);
    sent++;
    say("已补发 " + line.id + " → " + pane.pane_id);
  });
  if (sent) saveRegistry(reg);
  else say("没有可补发的排队派单。");
  return 0;
}

function refreshLines(reg, live, readChanged) {
  const byId = {};
  live.panes.forEach(function (p) { byId[p.pane_id] = p; });
  let changed = 0;
  let readBudget = readChanged ? 6 : 0;
  reg.lines.forEach(function (line) {
    if (["已验收", "已打回", "已取消"].indexOf(line.status) >= 0) return;
    const p = byId[line.target_pane];
    if (!p) {
      if (line.status !== "已取消") {
        line.status = "已取消";
        line.notes = "目标 pane 已不存在（被关闭或 Herdr 重启）。";
        pushEvent(line, "pane 消失", line.notes);
      }
      return;
    }
    const key = progressKey(p);
    if (line.last_progress_key !== key) {
      line.last_progress_key = key;
      line.last_change_at = nowIso();
      line.last_agent_status = p.agent_status;
      pushEvent(line, "输出更新", p.agent_status);
      changed++;
      if (readBudget > 0) {
        readBudget--;
        line.last_excerpt = excerptTail(p.pane_id);
      }
    }
    const before = line.status;
    if (p.agent_status === "blocked") {
      line.status = "受阻";
      line.notes = "代理停在审批或提问界面，需要你处理。";
    } else if (p.agent_status === "working") {
      if (["已发", "进行中", "待验收", "受阻"].indexOf(line.status) >= 0) line.status = "进行中";
      const idleMs = line.last_change_at ? Date.now() - new Date(line.last_change_at).getTime() : 0;
      if (idleMs > STALL_MS) {
        line.stalled = true;
        line.notes = "连续 " + Math.round(idleMs / 60000) + " 分钟输出无变化，疑似卡住。";
      } else {
        line.stalled = false;
        if (line.status === "进行中") line.notes = "";
      }
    } else if (isIdleStatus(p.agent_status)) {
      line.stalled = false;
      if (["已发", "进行中"].indexOf(line.status) >= 0) {
        line.status = "待验收";
        line.notes = "代理已空闲，等待验收。";
        pushEvent(line, "待验收", "代理空闲");
        // 刚转待验收时补一次干净摘录，验收时有话可读。
        if (readBudget > 0) { readBudget--; line.last_excerpt = excerptTail(p.pane_id); }
      }
    }
    if (before !== line.status) pushEvent(line, "状态变化", before + " → " + line.status);
  });
  return changed;
}

function buildTree(lines) {
  const byParent = {};
  const roots = [];
  lines.forEach(function (l) {
    if (l.parent_id) { byParent[l.parent_id] = byParent[l.parent_id] || []; byParent[l.parent_id].push(l); }
    else roots.push(l);
  });
  const out = [];
  function walk(list, depth) {
    list.forEach(function (l) {
      out.push({ line: l, depth: depth });
      walk(byParent[l.id] || [], depth + 1);
    });
  }
  walk(roots, 0);
  return out;
}

function reportMarkdown(live, reg, d, windowMin, ownerOnly) {
  const lines = reg.lines.filter(function (l) { return ownerOnly ? l.owner_session === OWNER : true; });
  const active = lines.filter(function (l) { return ["已验收", "已打回", "已取消"].indexOf(l.status) < 0; });
  const blocked = active.filter(function (l) { return l.status === "受阻" || l.stalled; });
  const waiting = active.filter(function (l) { return l.status === "待验收"; });
  const queued = active.filter(function (l) { return l.status === "待发"; });
  const managedIds = {};
  active.forEach(function (l) { managedIds[l.target_pane] = true; });
  const unmanagedChanged = d.changed.filter(function (c) { return !managedIds[c.pane.pane_id]; });
  const running = active.filter(function (l) { return l.status === "进行中" || l.status === "已发"; }).length;
  const summary = "本机 " + live.panes.length + " 个 pane、" + live.panes.filter(function (p) { return p.agent; }).length + " 个代理；受管 " + active.length + " 条（进行中 " + running + " / 待验收 " + waiting.length + " / 受阻 " + blocked.length + " / 排队 " + queued.length + "）。";
  const md = [];
  md.push("# Herdr 窗口汇报 " + stamp());
  md.push("");
  md.push("总控：" + OWNER + "　采样：" + stamp(new Date(live.taken_at)) + "　窗口：近 " + windowMin + " 分钟");
  md.push("");
  md.push("一句话总览：" + summary);
  md.push("");
  md.push("## 工作线");
  md.push("");
  if (!active.length) {
    md.push("（本总控暂无在途工作线。）");
  } else {
    md.push("| 项目 | pane | 代理 | 状态 | 近 " + windowMin + " 分钟进展 | 下一步 |");
    md.push("|---|---|---|---|---|---|");
    buildTree(active).forEach(function (node) {
      const l = node.line;
      const pane = live.panes.find(function (p) { return p.pane_id === l.target_pane; });
      const name = l.project_dir ? path.basename(l.project_dir) : "-";
      const indent = node.depth ? "└ ".repeat(node.depth) : "";
      const changedPane = d.changed.some(function (c) { return c.pane.pane_id === l.target_pane; });
      const progress = changedPane
        ? "有更新（" + minutesAgo(l.last_change_at) + "）" + (l.last_excerpt ? "：" + l.last_excerpt.slice(0, 60) : "")
        : (l.last_change_at ? "无变化（上次 " + minutesAgo(l.last_change_at) + "）" : "尚无输出");
      let next = "等汇报";
      if (l.status === "待发") next = "空闲后补发";
      else if (l.status === "待验收") next = "回读结果验收";
      else if (l.status === "受阻") next = "需要你处理";
      else if (l.status === "进行中" && l.stalled) next = "疑似卡住，建议查看";
      md.push("| " + indent + name + " | " + l.target_pane + " | " + ((pane && pane.agent) || "-") + " | " + l.status + " | " + progress + " | " + next + " |");
    });
  }
  md.push("");
  md.push("## 未受管窗口");
  md.push("");
  const unmanaged = live.panes.filter(function (p) { return !managedIds[p.pane_id]; });
  md.push(unmanaged.length + " 个 pane 不在本总控台账内。本期有变化 " + unmanagedChanged.length + " 个。");
  unmanagedChanged.slice(0, 8).forEach(function (c) {
    const p = c.pane;
    md.push("- " + p.workspace + " " + p.pane_id + " " + (p.agent || "shell") + " " + p.agent_status + "：" + (p.title || p.foreground_cwd));
  });
  md.push("");
  md.push("## 需要你处理");
  md.push("");
  const todo = [];
  blocked.forEach(function (l) {
    todo.push("- " + l.target_pane + " 「" + l.title + "」" + (l.stalled ? "疑似卡住：" : "受阻：") + (l.notes || "查看 pane 尾部"));
  });
  waiting.forEach(function (l) {
    todo.push("- " + l.target_pane + " 「" + l.title + "」已空闲，等我验收；要我验收回“验收 " + l.id + "”。");
  });
  queued.forEach(function (l) {
    todo.push("- " + l.target_pane + " 「" + l.title + "」在排队，目标空闲后我自动补发。");
  });
  if (!todo.length) todo.push("- 无。");
  md.push(todo.join("\n"));
  md.push("");
  return {
    markdown: md.join("\n"),
    summary: summary,
    blocked: blocked,
    waiting: waiting,
    queued: queued,
    hasChange: d.changed.length > 0 || d.added.length > 0
  };
}

function pruneReports() {
  if (!fs.existsSync(REPORT_DIR)) return;
  const cutoff = Date.now() - 7 * 24 * 60 * 60 * 1000;
  fs.readdirSync(REPORT_DIR).forEach(function (day) {
    const p = path.join(REPORT_DIR, day);
    try {
      const st = fs.statSync(p);
      if (st.isDirectory() && st.mtimeMs < cutoff) fs.rmSync(p, { recursive: true, force: true });
    } catch (e) {}
  });
}

function pushNotice(summary, dryRun) {
  const msg = "Herdr 汇报 " + stamp() + "：" + summary;
  const args = ["send", "--harness", NOTIFY_HARNESS, "--message", msg];
  if (dryRun) args.push("--dry-run");
  const r = spawnSync("harness-notify", args, { encoding: "utf8", timeout: 30000 });
  if (r.error) { say("推送失败：harness-notify 不可用（" + r.error.message + "）。"); return false; }
  const out = ((r.stdout || "") + (r.stderr || "")).trim();
  say("推送（" + (dryRun ? "预演" : "实际") + "）：" + (out ? out.split("\n").slice(0, 6).join(" | ") : "退出码 " + r.status));
  return r.status === 0;
}

function cmdReport(args) {
  const live = readLive();
  const prev = readPrevSnapshot();
  const d = diffPanes(prev, live);
  writeSnapshot(live);
  const reg = loadRegistry();
  const windowMin = args.since ? Number(args.since) : 20;
  const changedCount = refreshLines(reg, live, true);
  saveRegistry(reg);
  const built = reportMarkdown(live, reg, d, windowMin, !args["all-owners"]);
  const day = new Date();
  const dir = path.join(REPORT_DIR, day.getFullYear() + "-" + pad(day.getMonth() + 1) + "-" + pad(day.getDate()));
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, pad(day.getHours()) + pad(day.getMinutes()) + ".md");
  fs.writeFileSync(file, built.markdown);
  pruneReports();
  if (args.quiet) say("报告已写入 " + file + "（" + changedCount + " 条工作线有更新）");
  else { say(built.markdown); say("报告已写入 " + file); }
  const needPush = built.blocked.length > 0 || built.waiting.length > 0 || built.hasChange;
  if (args.push) {
    if (needPush || args["force-push"]) pushNotice(built.summary + " 详情 " + file, !!args["dry-run"]);
    else say("本次无变化、无受阻，按要求不推送。");
  }
  return 0;
}

function cmdLs(args) {
  const live = readLive();
  const reg = loadRegistry();
  const ownerOnly = !args["all-owners"];
  const lines = reg.lines.filter(function (l) { return ownerOnly ? l.owner_session === OWNER : true; });
  if (!lines.length) { say("本总控（" + OWNER + "）暂无台账记录。"); return 0; }
  say(["id", "项目", "pane", "代理", "状态", "工作线", "最近变化"].join("\t"));
  buildTree(lines).forEach(function (node) {
    const l = node.line;
    const p = live.panes.find(function (x) { return x.pane_id === l.target_pane; }) || {};
    say([
      l.id,
      l.project_dir ? path.basename(l.project_dir) : "-",
      l.target_pane || "-",
      p.agent || "-",
      l.status,
      "  ".repeat(node.depth) + l.title,
      minutesAgo(l.last_change_at) || "-"
    ].join("\t"));
  });
  return 0;
}

function cmdAck(args) {
  const id = flag(args, "id") || args._[0];
  const verdict = flag(args, "verdict") || (args.accept ? "accept" : args.reject ? "reject" : null);
  if (!id) die(2, "用法：hub.mjs ack <id> --verdict accept|reject [--evidence 回读到的证据] [--notes 说明]");
  if (verdict !== "accept" && verdict !== "reject") die(2, "--verdict 只能是 accept 或 reject。");
  const reg = loadRegistry();
  const line = findLine(reg, id);
  if (!line) die(1, "找不到工作线 " + id + "。用 hub.mjs ls 看现有记录。");
  const evidence = flag(args, "evidence");
  if (verdict === "accept" && !evidence) {
    die(2, "验收要留证据：加 --evidence（回读到什么：pane 尾部关键行、检查过的文件或命令）。没有证据就标未验证，不要写已验收。");
  }
  line.status = verdict === "accept" ? "已验收" : "已打回";
  line.verdict = verdict;
  line.decided_at = nowIso();
  line.evidence = evidence || null;
  line.notes = flag(args, "notes") || line.notes || "";
  pushEvent(line, verdict === "accept" ? "已验收" : "已打回", line.notes);
  saveRegistry(reg);
  say("已记录：" + line.id + " 「" + line.title + "」→ " + line.status);
  return 0;
}

function cmdRegister(args) {
  const title = flag(args, "title");
  const targetPane = flag(args, "target-pane");
  const project = flag(args, "project");
  if (!title || !targetPane) die(2, "用法：hub.mjs register --title <工作线> --target-pane <pane_id> [--project <目录>] [--status 已发] [--parent-id <父线id>] [--notes ...]");
  const status = flag(args, "status") || "已发";
  if (STATUSES.indexOf(status) < 0) die(2, "--status 只能是：" + STATUSES.join("、"));
  const reg = loadRegistry();
  const line = {
    id: newId(),
    owner_session: flag(args, "owner") || OWNER,
    parent_id: flag(args, "parent-id") || null,
    dispatcher_pane: flag(args, "parent-pane") || OWNER,
    target_pane: targetPane,
    project_dir: project ? resolveDir(project) : "",
    title: title,
    status: status,
    criteria: flag(args, "criteria") || "",
    prompt_file: flag(args, "prompt-file") || null,
    created_at: nowIso(),
    sent_at: nowIso(),
    last_progress_key: null,
    last_change_at: null,
    verdict: null,
    decided_at: null,
    notes: flag(args, "notes") || "子会话自查登记",
    events: []
  };
  pushEvent(line, "登记", "来自 " + line.owner_session);
  reg.lines.push(line);
  saveRegistry(reg);
  say("已登记 " + line.id + "：" + title + " → " + targetPane);
  return 0;
}

// pid 可能被系统复用：杀之前必须确认它还是我们的 watch 进程。
function pidAlive(pid) {
  try { process.kill(pid, 0); return true; } catch (e) { return false; }
}

function isHubWatch(pid) {
  if (!pidAlive(pid)) return false;
  const res = spawnSync("ps", ["-p", String(pid), "-o", "command="], { encoding: "utf8" });
  const cmdline = (res.stdout || "").trim();
  return cmdline.indexOf("hub.mjs") >= 0 && /\bwatch\b/.test(cmdline);
}

function readPidFile() {
  if (!fs.existsSync(PID_FILE)) return null;
  const pid = Number(fs.readFileSync(PID_FILE, "utf8").trim());
  return Number.isFinite(pid) && pid > 0 ? pid : null;
}

async function cmdWatch(args) {
  const minutes = Number(flag(args, "interval") || 20);
  if (!(minutes > 0)) die(2, "--interval 必须是正数（分钟）。");
  fs.mkdirSync(STATE_DIR, { recursive: true });
  const running = readPidFile();
  if (running && isHubWatch(running)) {
    die(2, "已有守护进程在跑（pid " + running + "）。先 hub.mjs stop 再启动，避免双开。");
  }
  if (running) { try { fs.unlinkSync(PID_FILE); } catch (e) {} }
  fs.writeFileSync(PID_FILE, String(process.pid));
  let stop = false;
  process.on("SIGINT", function () { stop = true; say("收到中断，收尾退出。"); });
  process.on("SIGTERM", function () { stop = true; });
  say("守护启动：每 " + minutes + " 分钟汇报一次，pid " + process.pid + "。");
  while (!stop) {
    try {
      cmdReport({ push: args.push, quiet: true, "dry-run": args["dry-run"], "all-owners": args["all-owners"] });
    } catch (e) { say("本轮汇报失败：" + e.message); }
    const until = Date.now() + minutes * 60 * 1000;
    while (!stop && Date.now() < until) await new Promise(function (r) { setTimeout(r, 5000); });
  }
  try { fs.unlinkSync(PID_FILE); } catch (e) {}
  return 0;
}

function cmdStop() {
  const pid = readPidFile();
  if (!pid) {
    try { fs.unlinkSync(PID_FILE); } catch (e) {}
    say("没有记录中的守护进程。");
    return 0;
  }
  if (!isHubWatch(pid)) {
    try { fs.unlinkSync(PID_FILE); } catch (e) {}
    say("pid " + pid + " 不是本工具的守护进程（可能已退出或 pid 被复用），只清理了 pid 文件，没有发信号。");
    return 0;
  }
  try { process.kill(pid, "SIGTERM"); } catch (e) { die(1, "停止失败：" + e.message); }
  // 等它自己收尾（最多 5 秒），再清 pid 文件，避免残留指向已退出进程。
  const until = Date.now() + 5000;
  while (Date.now() < until && pidAlive(pid)) {
    spawnSync("sleep", ["0.2"]);
  }
  try { fs.unlinkSync(PID_FILE); } catch (e) {}
  say("已停止守护进程 " + pid + "。");
  return 0;
}

function usage() {
  say([
    "weicoz-herdr-hub",
    "",
    "  hub.mjs init                       建状态目录",
    "  hub.mjs snapshot [--json]          采样全部 pane，并与上次采样对比",
    "  hub.mjs dispatch --title T --criteria C --prompt P|--prompt-file F",
    "                   [--pane ID | --project DIR [--new]] [--force-send]",
    "  hub.mjs flush                      发出排队的派单",
    "  hub.mjs report [--push] [--dry-run] [--since N] [--quiet] [--all-owners]",
    "  hub.mjs ls [--all-owners]          列台账",
    "  hub.mjs ack <id> --verdict accept|reject --evidence ... [--notes ...]",
    "  hub.mjs register --title T --target-pane ID [--project DIR] [--status S] [--parent-id ID]",
    "  hub.mjs watch [--interval 20] [--push] [--dry-run]   常驻循环",
    "  hub.mjs stop                       停掉 watch",
    "",
    "环境变量：WEICOZ_HERDR_HUB_STATE_DIR / WEICOZ_HERDR_HUB_OWNER / WEICOZ_HERDR_HUB_NOTIFY_HARNESS / WEICOZ_HERDR_HUB_STALL_MINUTES",
    "状态词：" + STATUSES.join("、"),
    "退出码：0 成功；1 错误；2 需要你补信息；3 目录冲突已拒绝"
  ].join("\n"));
}

async function main() {
  const parsed = parseArgs(process.argv.slice(2));
  const cmd = parsed._[0];
  // 各命令处理函数只看位置参数（去掉命令名本身），否则 ack <id> 会把命令名当 id。
  const args = Object.assign({}, parsed, { _: parsed._.slice(1) });
  if (!cmd || cmd === "help" || args.help) { usage(); return 0; }
  if (cmd === "init") return cmdInit();
  if (cmd === "snapshot") return cmdSnapshot(args);
  if (cmd === "dispatch") return cmdDispatch(args);
  if (cmd === "flush") return cmdFlush(args);
  if (cmd === "report") return cmdReport(args);
  if (cmd === "ls") return cmdLs(args);
  if (cmd === "ack") return cmdAck(args);
  if (cmd === "register") return cmdRegister(args);
  if (cmd === "watch") return cmdWatch(args);
  if (cmd === "stop") return cmdStop();
  usage();
  return 2;
}

main().then(function (code) { process.exit(code || 0); }).catch(function (e) {
  process.stderr.write("错误：" + (e && e.stack ? e.stack : e) + "\n");
  process.exit(1);
});
