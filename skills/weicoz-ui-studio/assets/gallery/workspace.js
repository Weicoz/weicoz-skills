const projects = [
  {
    id: "snow",
    blocks: 2,
    dueOrder: 1026,
    name: "雪中椿",
    owner: "林青",
    state: "进行中",
    quantity: 40,
    paper: "楮皮纸",
    due: "10 月 26 日",
    image: "media/sparrows-snow.webp",
    description: "第二版红色偏暖。压印前先对一张样张，十字线对准再开机。",
  },
  {
    id: "red",
    blocks: 0,
    dueOrder: 1031,
    name: "红椿复刻",
    owner: "夏禾",
    state: "待开始",
    quantity: 90,
    paper: "楮皮纸",
    due: "10 月 31 日",
    image: "media/red-camellia.webp",
    description: "印友会十月限定。每张需要手写编号，并在左下角钤印。",
  },
  {
    id: "vase",
    blocks: 4,
    dueOrder: 1020,
    name: "铜瓶梅椿",
    owner: "陈述",
    state: "已完成",
    quantity: 24,
    paper: "竹纸",
    due: "10 月 20 日",
    image: "media/vase.webp",
    description: "四块版全部套完，已晾干。等装裱师来取。",
  },
  {
    id: "night",
    blocks: 0,
    dueOrder: 1104,
    name: "燕与椿",
    owner: "周岩",
    state: "待开始",
    quantity: 30,
    paper: "竹纸",
    due: "11 月 4 日",
    image: "media/swallow-night.webp",
    description: "墨底面积大，先在竹纸上试一张，看墨会不会洇出边线。",
  },
  {
    id: "plum",
    blocks: 1,
    dueOrder: 1029,
    name: "梅枝小品",
    owner: "陈述",
    state: "进行中",
    quantity: 50,
    paper: "竹纸",
    due: "10 月 29 日",
    image: "media/blue-bird.webp",
    description: "墨版已经对好，下一块是靛版。枝干细，压力要轻。",
  },
  {
    id: "basket",
    blocks: 0,
    dueOrder: 1108,
    name: "冬篮",
    owner: "夏禾",
    state: "待开始",
    quantity: 60,
    paper: "楮皮纸",
    due: "11 月 8 日",
    image: "media/winter-basket.webp",
    description: "江南彩印，颜色多。先刻墨版，再定其余各块版的分版。",
  },
];
// 四块版按顺序套：墨、靛、绿、红。状态由已套块数决定，不单独跳。
const BLOCKS = ["墨", "靛", "绿", "红"];
const stateOf = (blocks) =>
  blocks === 0 ? "待开始" : blocks === 4 ? "已完成" : "进行中";
const undoStack = [];
const $ = (selector) => document.querySelector(selector);
const reduced = matchMedia("(prefers-reduced-motion: reduce)");
// 换成页面里静态图片的实际地址；在对比页里它们已被内嵌成 data URI。
const covers = new Map(
  [...document.querySelectorAll("#covers img")].map((img) => [img.dataset.path, img.src]),
);
projects.forEach((p) => (p.image = covers.get(p.image) ?? p.image));
// 回执只属于写下它的那张订单；选中项无论怎样改变，都在渲染时清掉旧回执。
let receiptFor = null;
function receipt(project, text) {
  receiptFor = project.id;
  $("#workspace-result").textContent = text;
}
const states = ["待开始", "进行中", "已完成"];
const params = new URLSearchParams(location.search);
let selected =
  projects.find((p) => p.id === params.get("selected"))?.id || projects[0].id;
["search", "status-filter", "layout", "sort"].forEach((id) => {
  const value = params.get(id);
  if (value !== null) $("#" + id).value = value;
});
if (!$("#layout").value) $("#layout").value = "list";
if (!$("#status-filter").value) $("#status-filter").value = "all";
if (!$("#sort").value) $("#sort").value = "due";
let urgentId = null;
function buttonFor(project) {
  const button = document.createElement("button");
  button.className = "project-row";
  button.dataset.state = project.state;
  button.dataset.id = project.id;
  if (project.id === urgentId) button.dataset.urgent = "true";
  button.setAttribute("aria-pressed", project.id === selected);
  const thumb = document.createElement("img");
  thumb.src = project.image;
  thumb.alt = "";
  const text = document.createElement("span");
  const strong = document.createElement("strong");
  strong.textContent = project.name;
  const small = document.createElement("small");
  // 分段写入：看板里可以只隐藏纸张，交期整段不断行。
  [
    [project.owner, ""],
    [` · ${project.quantity} 张`, ""],
    [` · ${project.paper}`, "paper"],
    [` · ${project.due}`, "due"],
  ].forEach(([value, className]) => {
    const part = document.createElement("span");
    part.textContent = value;
    if (className) part.className = className;
    small.append(part);
  });
  text.append(strong, small);
  const state = document.createElement("em");
  state.textContent = project.state;
  button.append(thumb, text, state);
  button.onclick = () => {
    selected = project.id;
    $("#workspace").classList.add("show-detail");
    render(true);
    $("#inspector").classList.remove("entering");
    void $("#inspector").offsetWidth;
    $("#inspector").classList.add("entering");
    $("#detail-title").tabIndex = -1;
    $("#detail-title").focus();
  };
  return button;
}
function saveURL(push = false) {
  // 离线对比页使用不透明 srcdoc，状态仍可操作，但没有可写的页面 URL。
  if (location.protocol === "about:") return;
  const p = new URLSearchParams();
  ["search", "status-filter", "layout", "sort"].forEach((id) =>
    p.set(id, $("#" + id).value),
  );
  p.set("selected", selected);
  history[push ? "pushState" : "replaceState"](null, "", "?" + p);
}
function render(push = false) {
  const query = $("#search").value.trim().toLowerCase();
  const filter = $("#status-filter").value;
  const visible = projects
    .filter(
      (p) =>
        (p.name + p.owner).toLowerCase().includes(query) &&
        (filter === "all" || p.state === filter),
    )
    .sort((a, b) =>
      $("#sort").value === "due"
        ? // 未完成的按交期在前，已完成的沉到最后。
          (a.blocks === 4) - (b.blocks === 4) || a.dueOrder - b.dueOrder
        : a.name.localeCompare(b.name, "zh-CN") *
          ($("#sort").value === "desc" ? -1 : 1),
    );
  // 还没套完、交期最近的一单标为“最急”。
  // 在全部订单里算，不受搜索和筛选影响，和顶部“最近交期”一致。
  const urgent = projects
    .filter((p) => p.blocks < 4)
    .sort((a, b) => a.dueOrder - b.dueOrder)[0]?.id;
  urgentId = urgent;
  if (!visible.some((p) => p.id === selected) && visible.length)
    selected = visible[0].id;
  const layout = $("#layout").value;
  const layoutChanged = $("#workspace").dataset.layout !== layout;
  $("#workspace").dataset.layout = layout;
  const items = $("#items");
  // FLIP：记下每行原来的位置，渲染后从原位滑到新位置，看得出它移到了哪里。
  const before = new Map(
    [...items.querySelectorAll(".project-row")].map((row) => [
      row.dataset.id,
      row.getBoundingClientRect().top,
    ]),
  );
  items.replaceChildren();
  if (layout === "board") {
    const board = document.createElement("div");
    board.className = "board";
    states.forEach((state) => {
      const col = document.createElement("section");
      col.className = "column";
      const heading = document.createElement("h2");
      heading.textContent = `${state} · ${visible.filter((p) => p.state === state).length}`;
      col.append(heading);
      const matching = visible.filter((p) => p.state === state);
      matching.forEach((p) => col.append(buttonFor(p)));
      if (!matching.length) {
        const empty = document.createElement("p");
        empty.textContent = `没有${state}的订单`;
        col.append(empty);
      }
      board.append(col);
    });
    items.append(board);
  } else if (layout === "table") {
    const wrap = document.createElement("div");
    wrap.className = "table-wrap";
    wrap.tabIndex = 0;
    wrap.setAttribute("aria-label", "订单表格");
    const table = document.createElement("table");
    table.innerHTML =
      '<thead><tr><th scope="col">订单</th><th scope="col">负责人</th><th scope="col" class="wide-only">数量</th><th scope="col" class="wide-only">交期</th><th scope="col">状态</th></tr></thead>';
    const body = document.createElement("tbody");
    visible.forEach((p) => {
      const tr = document.createElement("tr");
      const name = document.createElement("td");
      const button = buttonFor(p);
      button.className = "";
      button.replaceChildren(document.createTextNode(p.name));
      name.append(button);
      tr.append(name);
      [
        [p.owner, ""],
        [`${p.quantity} 张`, "wide-only"],
        [p.due, "wide-only"],
        [p.state, "state-cell"],
      ].forEach(([value, className]) => {
        const td = document.createElement("td");
        td.textContent = value;
        if (className) td.className = className;
        if (className === "state-cell") td.dataset.state = p.state;
        tr.append(td);
      });
      body.append(tr);
    });
    table.append(body);
    wrap.append(table);
    items.append(wrap);
  } else
    visible.forEach((p, index) => {
      // 按交期排时，已完成的单另起一组，沉在最后。
      if ($("#sort").value === "due" && p.blocks === 4 && visible[index - 1]?.blocks !== 4) {
        const label = document.createElement("p");
        label.className = "group-label";
        label.textContent = `已完成 · ${visible.filter((q) => q.blocks === 4).length}`;
        items.append(label);
      }
      items.append(buttonFor(p));
    });
  if (!visible.length) {
    const empty = document.createElement("p");
    empty.textContent = "没有对得上的订单。换个关键词，或把状态改回“全部”。";
    items.append(empty);
  }
  const project = visible.find((p) => p.id === selected);
  if (receiptFor !== project?.id) {
    receiptFor = null;
    $("#workspace-result").textContent = "";
  }
  $("#inspector").hidden = !project;
  if (!project) $("#workspace").classList.remove("show-detail");
  if (project) {
    $("#detail-title").textContent = project.name;
    $("#detail-image").src = project.image;
    $("#detail-image").alt = `${project.name}图版`;
    $("#detail-owner").textContent = project.owner;
    $("#detail-quantity").textContent = `${project.quantity} 张`;
    $("#detail-paper").textContent = project.paper;
    $("#detail-due").textContent = project.due;
    $("#detail-state").textContent = "状态：" + project.state;
    $("#detail-state").dataset.state = project.state;
    $("#detail-description").textContent =
      project.blocks === 4
        ? "四块版都已套完，正在晾干。"
        : project.description;
    const done = project.blocks;
    document.querySelectorAll("#blocks li").forEach((li, index) => {
      li.dataset.done = String(index < done);
    });
    $("#blocks-label").textContent =
      done === 4 ? "四块版全部套完" : `已套 ${done} / 4 块版`;
    $("#move").disabled = done === 4;
    $("#move").textContent =
      done === 4 ? "四块版已套完" : `套完${BLOCKS[done]}版`;
    $("#undo").hidden = !undoStack.some((step) => step.id === project.id);
    $("#detail-next").textContent =
      done === 4 ? "下一步：晾干后交给装裱师。" : `下一步：套${BLOCKS[done]}版。`;
  }
  $("#results").textContent = `${visible.length} 张订单`;
  // 顶部汇总跟着进度变。
  const open = projects.filter((p) => p.blocks < 4);
  $("#sum-open").textContent = open.length;
  $("#sum-prints").textContent = open.reduce((sum, p) => sum + p.quantity, 0);
  $("#sum-due").textContent = open.length
    ? [...open].sort((a, b) => a.dueOrder - b.dueOrder)[0].due
    : "全部完成";
  if (!reduced.matches) {
    if (layoutChanged) items.animate([{ opacity: 0, transform: "translateY(6px)" }, { opacity: 1, transform: "none" }], { duration: 240, easing: "ease-out" });
    else
      items.querySelectorAll(".project-row").forEach((row) => {
        const top = before.get(row.dataset.id);
        const delta = top === undefined ? 0 : top - row.getBoundingClientRect().top;
        if (Math.abs(delta) > 1)
          row.animate([{ transform: `translateY(${delta}px)` }, { transform: "none" }], {
            duration: 360,
            easing: "cubic-bezier(0.2, 0.8, 0.2, 1)",
          });
      });
  }
  saveURL(push);
}
["search", "status-filter", "layout", "sort"].forEach((id) =>
  $("#" + id).addEventListener(id === "search" ? "input" : "change", () => {
    $("#workspace").classList.remove("show-detail");
    render(id !== "search");
  }),
);
window.addEventListener("popstate", () => {
  const params = new URLSearchParams(location.search);
  selected =
    projects.find((p) => p.id === params.get("selected"))?.id || projects[0].id;
  ["search", "status-filter", "layout", "sort"].forEach((id) => {
    $("#" + id).value =
      params.get(id) ||
      { search: "", "status-filter": "all", layout: "list", sort: "due" }[id];
  });
  $("#workspace").classList.remove("show-detail");
  render();
});
$("#move").onclick = () => {
  const p = projects.find((p) => p.id === selected);
  if (p.blocks >= 4) return;
  undoStack.push({ id: p.id, blocks: p.blocks });
  p.blocks++;
  p.state = stateOf(p.blocks);
  receipt(p, `${p.name}：已套完${BLOCKS[p.blocks - 1]}版，${p.state}。`);
  render();
  $("#inspector").classList.remove("stepped");
  void $("#inspector").offsetWidth;
  $("#inspector").classList.add("stepped");
};
$("#undo").onclick = () => {
  const index = undoStack.findLastIndex((step) => step.id === selected);
  if (index < 0) return;
  const [step] = undoStack.splice(index, 1);
  const p = projects.find((p) => p.id === step.id);
  p.blocks = step.blocks;
  p.state = stateOf(p.blocks);
  receipt(p, `已撤销：${p.name}回到${p.state}，已套 ${p.blocks} / 4 块版。`);
  render();
  $("#move").focus();
};
$("#back-list").onclick = () => {
  $("#workspace").classList.remove("show-detail");
  $("#items button")?.focus();
};
render();
