const projects = [
  {
    id: "reading",
    name: "河岸阅读计划",
    owner: "青禾",
    state: "进行中",
    description: "把每周的二十页，变成可以相约的下午。",
  },
  {
    id: "walk",
    name: "城市漫游",
    owner: "林青",
    state: "待开始",
    description: "以步行路线重新认识城市，先完成三条河岸路线。",
  },
  {
    id: "notes",
    name: "十月札记",
    owner: "陈述",
    state: "已完成",
    description: "收集十月的照片、声音与记忆，整理成开放的记录。",
  },
  {
    id: "poster",
    name: "书店海报",
    owner: "夏禾",
    state: "待开始",
    description: "为周末阅读活动设计一张清晰、醒目的海报。",
  },
];
const $ = (selector) => document.querySelector(selector);
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
if (!$("#sort").value) $("#sort").value = "asc";
function buttonFor(project) {
  const button = document.createElement("button");
  button.className = "project-row";
  button.setAttribute("aria-pressed", project.id === selected);
  const strong = document.createElement("strong");
  strong.textContent = project.name;
  const small = document.createElement("small");
  small.textContent = `${project.owner} · ${project.state}`;
  button.append(strong, small);
  button.onclick = () => {
    selected = project.id;
    $("#workspace").classList.add("show-detail");
    render(true);
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
    .sort(
      (a, b) =>
        a.name.localeCompare(b.name, "zh-CN") *
        ($("#sort").value === "desc" ? -1 : 1),
    );
  if (!visible.some((p) => p.id === selected) && visible.length)
    selected = visible[0].id;
  const layout = $("#layout").value;
  $("#workspace").dataset.layout = layout;
  const items = $("#items");
  items.replaceChildren();
  if (layout === "board") {
    const board = document.createElement("div");
    board.className = "board";
    states.forEach((state) => {
      const col = document.createElement("section");
      col.className = "column";
      const heading = document.createElement("h2");
      heading.textContent = state;
      col.append(heading);
      const matching = visible.filter((p) => p.state === state);
      matching.forEach((p) => col.append(buttonFor(p)));
      if (!matching.length) {
        const empty = document.createElement("p");
        empty.textContent = "暂无项目";
        col.append(empty);
      }
      board.append(col);
    });
    items.append(board);
  } else if (layout === "table") {
    const wrap = document.createElement("div");
    wrap.className = "table-wrap";
    wrap.tabIndex = 0;
    wrap.setAttribute("aria-label", "项目表格，可横向滚动");
    const table = document.createElement("table");
    table.innerHTML =
      '<thead><tr><th scope="col">项目</th><th scope="col">负责人</th><th scope="col">状态</th></tr></thead>';
    const body = document.createElement("tbody");
    visible.forEach((p) => {
      const tr = document.createElement("tr");
      const name = document.createElement("td");
      const button = buttonFor(p);
      button.className = "";
      button.replaceChildren(document.createTextNode(p.name));
      name.append(button);
      tr.append(name);
      [p.owner, p.state].forEach((value) => {
        const td = document.createElement("td");
        td.textContent = value;
        tr.append(td);
      });
      body.append(tr);
    });
    table.append(body);
    wrap.append(table);
    items.append(wrap);
  } else visible.forEach((p) => items.append(buttonFor(p)));
  if (!visible.length) {
    const empty = document.createElement("p");
    empty.textContent = "没有匹配的项目，请调整筛选。";
    items.append(empty);
  }
  const project = visible.find((p) => p.id === selected);
  $("#inspector").hidden = !project;
  if (!project) $("#workspace").classList.remove("show-detail");
  if (project) {
    $("#detail-title").textContent = project.name;
    $("#detail-owner").textContent = "负责人：" + project.owner;
    $("#detail-state").textContent = "状态：" + project.state;
    $("#detail-description").textContent = project.description;
    $("#move").textContent =
      project.state === "已完成" ? "重新开始" : "推进状态";
  }
  $("#results").textContent = `${visible.length} 个项目`;
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
      { search: "", "status-filter": "all", layout: "list", sort: "asc" }[id];
  });
  $("#workspace").classList.remove("show-detail");
  render();
});
$("#move").onclick = () => {
  const p = projects.find((p) => p.id === selected);
  p.state = states[(states.indexOf(p.state) + 1) % states.length];
  $("#workspace-result").textContent = `${p.name}：${p.state}`;
  render();
};
$("#back-list").onclick = () => {
  $("#workspace").classList.remove("show-detail");
  $("#items button")?.focus();
};
render();
