const $ = (selector) => document.querySelector(selector);
const reduced = matchMedia("(prefers-reduced-motion: reduce)");
let paused = false;
let frame = null;
let active = true;
let ticks = 0;

// 网点：明暗与色版取自《红椿》（69×30）。数字是墨/叶版，A–J 是红版；0 为白纸，9 最深。
// 离线算好，避免 file:// 下读取图片像素污染画布。
const COLS = 69;
const ROWS = 30;
const HALFTONE =
  "000000000000000000000000000000000000000000000000000000000000000000000" +
  "000000000000000000000000000000000000000000000000000000000000000000000" +
  "000000000000000000000000000000000000000000000000000000000000000000000" +
  "000000000000000000000000000000000000000000000000000000000000000000000" +
  "000000000000011000000000000000000000000000000000000000000000000000000" +
  "000000000000345500000000000000000000000000000000000000000000000000000" +
  "000000000002531561000000000000000000000000000000000000000000000000000" +
  "000000000014100576200000000000000000000000000000000000000000000000000" +
  "000000000000000677740000000000000000000001000000000000000000000000000" +
  "0000000000000007877874100001000CDDC000001DC00000000000000000000000000" +
  "00000000000000188877898400CEDEFEFEEFD0DDDCC00000000367777642000000000" +
  "00000000000000388888789841DFGHFEFDCFE1EECCC11000258999888887520000000" +
  "0000000000000048887788987EEGGGHHFCFGDCEFDECCC105999888888888885100000" +
  "0000000000000058888777897DFGGGHFCCFGEEGFFDCDDCCE798889988888778820000" +
  "0000000000000058888887788DEFGGDEGFGEDHGHGEEEFFED499999998888888783000" +
  "000000000000004988887878HEDFGGEDEDFEEHHGEEFEDFHFFI8999989988889989300" +
  "00000000000000288877778GHFCEFGHIFFFHGGHEDEEDEDFFFGGH99999889999999841" +
  "00000000000000079887777FHIDDFGGIGFGHHFGGFDEEFGDGGEFG79999999988888875" +
  "00000000000000039888887FGJHCCDEHHEGFHGHHEEFGFEEGHGEGG9999989988888810" +
  "00000000000000007998897FGIJIHHHGHFGEIHHHEGGFEGFFHHGHG9999988888889500" +
  "0000000000000000199888HFGIJJJJJJIFFEIIFGHIHHHEEGHHFGF7999888887887100" +
  "0000000000000000039988FFIIJJIHJJJJHFIIGGGGIIHFGHGGFEF7999888888886000" +
  "0000000000000000003998HHIIJJHGHIJJJJIGFFEEFHHFGHGGEGF8988788888882000" +
  "0000000001467776420189IHHIJJIGHHIIJJJGFFEEEGGFHHGFHII9988888878950000" +
  "0000000378888889986315IHHIJJJGGGHHIJJIGFFFEFGGHHFGJH89988878888810000" +
  "0000016988888888888872DIHIIJJHFGGGHIJJJJJHHIIHGFFJJG79999888888700000" +
  "00004898888888888888885EHIIIJJGFFFGHIJIJJJJJIGFGJJJG79888888888100000" +
  "000499898898888888888885CHIIJJJHGIGFGHIHIIIHHHHHHIHG89887888883000000" +
  "0049999999999898988888886FJJJIIIJJIIIJJHFGGGFHHIGEH999998888940000000" +
  "04999988999999999988888886EHFFJHIIJJJIIJIGGGIJJJHG9999998888300000000";
const dots = $("#dots");
const ctx = dots.getContext("2d");
let pointer = { x: -1e4, y: -1e4 };
let dotsDirty = true;
dots.addEventListener("pointermove", (event) => {
  const box = dots.getBoundingClientRect();
  pointer = {
    x: ((event.clientX - box.left) / box.width) * dots.width,
    y: ((event.clientY - box.top) / box.height) * dots.height,
  };
  dotsDirty = true;
  if (frame === null) requestAnimationFrame(drawDots);
});
dots.addEventListener("pointerleave", () => {
  pointer = { x: -1e4, y: -1e4 };
  dotsDirty = true;
  requestAnimationFrame(drawDots);
});
function drawDots() {
  if (!ctx || !dotsDirty) return;
  dotsDirty = false;
  // 网距按高度算，网格在横幅里居中，两侧留纸。
  const pitch = dots.height / ROWS;
  const left = (dots.width - COLS * pitch) / 2;
  ctx.fillStyle = "#f1e9d8";
  ctx.fillRect(0, 0, dots.width, dots.height);
  for (let row = 0; row < ROWS; row++) {
    for (let col = 0; col < COLS; col++) {
      const cell = HALFTONE[row * COLS + col];
      const red = cell >= "A";
      const value = red ? cell.charCodeAt(0) - 65 : Number(cell);
      const x = left + (col + 0.5) * pitch;
      const y = (row + 0.5) * pitch;
      const distance = Math.hypot(x - pointer.x, y - pointer.y);
      // 放大镜：只放大网点，不移动位置，仍读得出原图的形状。
      const lens = reduced.matches ? 0 : Math.max(0, 1 - distance / 130);
      const radius = (0.6 + Math.sqrt(value / 9) * 0.46 * pitch) * (1 + lens * 0.75);
      ctx.beginPath();
      ctx.arc(x, y, radius, 0, Math.PI * 2);
      ctx.fillStyle = red
        ? "rgba(168, 48, 42, 0.9)"
        : value >= 6
          ? "rgba(36, 56, 45, 0.88)"
          : value > 0
            ? "rgba(29, 33, 30, 0.7)"
            : "rgba(29, 33, 30, 0.1)";
      ctx.fill();
    }
  }
  if (pointer.x > -1e3 && !reduced.matches) {
    // 放大镜的镜圈。
    ctx.beginPath();
    ctx.arc(pointer.x, pointer.y, 130, 0, Math.PI * 2);
    ctx.strokeStyle = "rgba(29, 33, 30, 0.35)";
    ctx.lineWidth = 2;
    ctx.stroke();
  }
}

// 墨洇：分形噪声扭曲距离场，干边略深，纸纤维横向。
const canvas = $("#shader");
let gl = null;
let uniforms = {};
try {
  gl = canvas.getContext("webgl", {
    antialias: false,
    preserveDrawingBuffer: true,
  });
  if (!gl) throw new Error("WebGL unavailable");
  const compile = (kind, source) => {
    const shader = gl.createShader(kind);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      gl.deleteShader(shader);
      throw new Error("shader compile failed");
    }
    return shader;
  };
  const vertex = compile(
    gl.VERTEX_SHADER,
    "attribute vec2 p; void main(){gl_Position=vec4(p,0.,1.);}",
  );
  const fragment = compile(
    gl.FRAGMENT_SHADER,
    `precision mediump float;
uniform vec2 r; uniform float t; uniform float seed;
float h(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7))+seed*17.3)*43758.5453);}
float n(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);
  return mix(mix(h(i),h(i+vec2(1,0)),f.x),mix(h(i+vec2(0,1)),h(i+1.),f.x),f.y);}
float fbm(vec2 p){float v=0.,a=.5;for(int k=0;k<5;k++){v+=a*n(p);p*=2.03;a*=.5;}return v;}
void main(){
  vec2 p=(gl_FragCoord.xy-.5*r)/r.y;
  vec2 c=vec2(sin(seed*2.1)*.18,cos(seed*1.7)*.06);
  float spread=.12+.32*(1.-exp(-t*.45));
  float w=fbm(p*3.2+fbm(p*7.+seed)*1.6);
  float d=length((p-c)*vec2(.92,1.1))+(w-.5)*.32;
  float ink=smoothstep(spread,spread-.1,d);
  float rim=smoothstep(spread-.035,spread-.005,d)*smoothstep(spread+.01,spread-.005,d);
  float fiber=fbm(vec2(p.x*46.,p.y*5.))*.07+fbm(p*120.)*.03;
  vec3 paper=vec3(.945,.914,.847)-fiber;
  vec3 indigo=vec3(.168,.282,.4);
  vec3 col=mix(paper,indigo*(.82+.3*w),ink*.86);
  col=mix(col,indigo*.62,rim*.7);
  gl_FragColor=vec4(col,1.);
}`,
  );
  const program = gl.createProgram();
  gl.attachShader(program, vertex);
  gl.attachShader(program, fragment);
  gl.linkProgram(program);
  gl.deleteShader(vertex);
  gl.deleteShader(fragment);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS))
    throw new Error("shader link failed");
  gl.useProgram(program);
  const buffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(
    gl.ARRAY_BUFFER,
    new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]),
    gl.STATIC_DRAW,
  );
  const location = gl.getAttribLocation(program, "p");
  gl.vertexAttribPointer(location, 2, gl.FLOAT, false, 0, 0);
  gl.enableVertexAttribArray(location);
  uniforms = {
    r: gl.getUniformLocation(program, "r"),
    t: gl.getUniformLocation(program, "t"),
    seed: gl.getUniformLocation(program, "seed"),
  };
  $("#shader-status").textContent = "WebGL 已就绪 · 墨的扩散实时计算";
} catch {
  gl = null;
  canvas.classList.add("unavailable");
  $("#shader-status").classList.add("problem");
  $("#shader-status").textContent = "WebGL 不可用，显示静态墨迹替代。";
}
canvas.addEventListener("webglcontextlost", (event) => {
  event.preventDefault();
  gl = null;
  canvas.classList.add("unavailable");
  $("#shader-status").classList.add("problem");
  $("#shader-status").textContent = "绘图上下文已中断，显示静态墨迹替代。";
});
const CYCLE = 12;
function drawInk() {
  if (!gl) return;
  const seconds = ticks / 60;
  // 减少动态效果：直接画扩散完成后的终态。
  const t = reduced.matches ? 9 : seconds % CYCLE;
  const seed = reduced.matches ? 1 : Math.floor(seconds / CYCLE) + 1;
  gl.viewport(0, 0, canvas.width, canvas.height);
  gl.uniform2f(uniforms.r, canvas.width, canvas.height);
  gl.uniform1f(uniforms.t, t);
  gl.uniform1f(uniforms.seed, seed);
  gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
}

// 刻线：一刀接一刀。每刀按长度分时间，刀内入刀慢、行刀快、收刀慢；刻完停一会，淡出重来。
const cuts = [...document.querySelectorAll(".light-path .cut")];
const tip = $(".light-path .tip");
const impression = $(".light-path .impression");
const lengths = cuts.map((path) => path.getTotalLength());
const totalLength = lengths.reduce((sum, value) => sum + value, 0);
cuts.forEach((path, i) => {
  path.style.strokeDasharray = `${lengths[i]} ${lengths[i]}`;
});
const CARVE = 9;
const ease = (x) => (x < 0.5 ? 4 * x * x * x : 1 - (-2 * x + 2) ** 3 / 2);
function drawCarve() {
  const u = reduced.matches ? 0.9 : ((ticks / 60) % CARVE) / CARVE;
  const carved = Math.min(1, u / 0.78) * totalLength;
  let start = 0;
  let point = null;
  cuts.forEach((path, i) => {
    const local = Math.max(0, Math.min(1, (carved - start) / lengths[i]));
    const done = ease(local) * lengths[i];
    path.style.strokeDashoffset = String(lengths[i] - done);
    if (local > 0 && local < 1) point = path.getPointAtLength(done);
    start += lengths[i];
  });
  const fade = u > 0.94 ? 1 - (u - 0.94) / 0.06 : 1;
  cuts.forEach((path) => (path.style.opacity = String(fade)));
  // 刻完才落一张试印，和刻痕一起淡出。
  if (impression)
    impression.style.opacity = String(Math.max(0, Math.min(1, (u - 0.8) / 0.06)) * fade);
  if (tip) {
    tip.style.opacity = point ? "1" : "0";
    if (point) {
      tip.setAttribute("cx", point.x.toFixed(1));
      tip.setAttribute("cy", point.y.toFixed(1));
    }
  }
}

// 套色对位
const bed = $(".press-bed");
const fixedOffsets = [6, -3, 10, -1, 4];
let offset = 14;
let phase = 0.6;
let score = 0;
let gamePaused = false;
const offsets = [];
let holdUntil = 0;
function moveLayer() {
  // 压下后色版停半秒，看清这一张印得怎样，再继续漂移。
  if (!gamePaused && score < 5 && performance.now() > holdUntil) {
    phase += 0.034;
    offset = Math.sin(phase) * 26 + Math.sin(phase * 2.3) * 6;
  }
  bed.style.setProperty("--offset", `${offset.toFixed(1)}px`);
}

function draw() {
  drawInk();
  drawDots();
  drawCarve();
}
function loop() {
  frame = null;
  if (!active || paused || reduced.matches || document.hidden) return;
  ticks++;
  drawInk();
  drawDots();
  drawCarve();
  moveLayer();
  frame = requestAnimationFrame(loop);
}
function sync() {
  if (frame !== null) {
    cancelAnimationFrame(frame);
    frame = null;
  }
  const still = paused || reduced.matches;
  document.body.dataset.paused = String(still);
  document.body.dataset.reduced = String(reduced.matches);
  $("#motion-toggle").setAttribute("aria-pressed", String(paused));
  $("#motion-toggle").disabled = reduced.matches;
  $("#motion-toggle").textContent = reduced.matches
    ? "动态效果已由系统关闭"
    : paused
      ? "恢复动态效果"
      : "暂停动态效果";
  $("#motion-status").textContent = reduced.matches
    ? "系统已开启减少动态效果，画面保持静态，停在完成后的样子。"
    : paused
      ? "动态效果已暂停。"
      : "动态效果正在播放，可随时暂停。";
  if (reduced.matches && score < 5) offset = fixedOffsets[score];
  bed.style.setProperty("--offset", `${offset.toFixed(1)}px`);
  dotsDirty = true;
  draw();
  if (active && !still && !document.hidden)
    frame = requestAnimationFrame(loop);
}
$("#motion-toggle").onclick = () => {
  paused = !paused;
  sync();
};
reduced.addEventListener("change", () => {
  sync();
  updateStory();
});
document.addEventListener("visibilitychange", sync);

let scrollFrame = null;
function updateStory() {
  scrollFrame = null;
  const story = $(".story");
  const box = story.getBoundingClientRect();
  const progress = Math.max(
    0,
    Math.min(
      1,
      (-box.top + innerHeight * 0.35) /
        Math.max(1, box.height - innerHeight * 0.9),
    ),
  );
  // 第一章只有墨版；第二、第三章的标题进入屏幕中段时，滚筒才刷上对应那一版。
  const [, second, third] = story.querySelectorAll(".story-chapters article");
  const arrive = (chapter) =>
    Math.max(0, Math.min(1, (innerHeight * 0.62 - chapter.getBoundingClientRect().top) / (innerHeight * 0.42)));
  let cool = arrive(second);
  let warm = arrive(third);
  if (reduced.matches) {
    // 不播滚筒：到了哪一章，就直接显示那一章的版。
    cool = cool > 0.5 ? 1 : 0;
    warm = warm > 0.5 ? 1 : 0;
  }
  const rolling = warm > 0 ? warm : cool;
  story.style.setProperty("--progress", progress.toFixed(3));
  story.style.setProperty("--cool", cool.toFixed(3));
  story.style.setProperty("--warm", warm.toFixed(3));
  story.style.setProperty("--roll", rolling.toFixed(3));
  story.style.setProperty("--roller", !reduced.matches && rolling > 0 && rolling < 1 ? 1 : 0);
  story.style.setProperty("--roll-ink", warm > 0 ? "#b8402f" : "#6f9a5c");
  $("#story-progress").value = progress;
}
function queueStory() {
  if (scrollFrame === null) scrollFrame = requestAnimationFrame(updateStory);
}
window.addEventListener("scroll", queueStory, { passive: true });
window.addEventListener("resize", queueStory);

function gameRender(message) {
  const done = score === 5;
  $("#target").disabled = done || gamePaused;
  $("#target").textContent = done ? "已印完" : "压印";
  const average = offsets.length
    ? (offsets.reduce((sum, value) => sum + value, 0) / offsets.length).toFixed(1)
    : 0;
  $("#game-status").textContent = done
    ? `5 / 5，完成。平均偏差 ${average} px，可以重新开始再印一轮。`
    : gamePaused
      ? `${score} / 5，练习已暂停。`
      : message || `${score} / 5，准备好就出发。`;
  $("#game-pause").setAttribute("aria-pressed", String(gamePaused));
  $("#game-pause").textContent = gamePaused ? "继续练习" : "暂停练习";
}
$("#target").onclick = () => {
  if (gamePaused || score >= 5) return;
  const miss = Math.abs(offset);
  holdUntil = performance.now() + 520;
  offsets.push(miss);
  score++;
  // 把这一张真的“印”出来：同样的两块版，按这次的偏差错开。
  const item = $("#prints").children[score - 1];
  item.className = "";
  item.dataset.grade = miss <= 3 ? "good" : "off";
  item.style.setProperty("--miss", `${offset.toFixed(1)}px`);
  // 用页面里已有图片的地址，对比页内嵌后仍能显示。
  const art = $(".layer-key").src;
  item.innerHTML = `<div class="sheet"><img class="layer-key" src="${art}" alt="" /><img class="layer-red" src="${art}" alt="" /></div><span>第 ${score} 张 · <b>${miss.toFixed(1)} px</b></span>`;
  item.querySelector(".sheet").setAttribute("aria-label", `第 ${score} 张，偏差 ${miss.toFixed(1)} 像素`);
  $("#press-note").dataset.grade = item.dataset.grade;
  $("#press-note").textContent = miss <= 3 ? "对准了。" : `偏了 ${miss.toFixed(1)} px。`;
  bed.classList.remove("pressed");
  void bed.offsetWidth;
  bed.classList.add("pressed");
  if (reduced.matches && score < 5) {
    offset = fixedOffsets[score];
    bed.style.setProperty("--offset", `${offset}px`);
  }
  gameRender(
    `${score} / 5，这张偏差 ${miss.toFixed(1)} px${miss <= 3 ? "，对准了" : "，红版偏了"}。`,
  );
  if (score === 5) $("#game-reset").focus();
};
$("#game-pause").onclick = () => {
  gamePaused = !gamePaused;
  gameRender();
};
$("#game-reset").onclick = () => {
  score = 0;
  gamePaused = false;
  offsets.length = 0;
  resetSlots();
  if (reduced.matches) offset = fixedOffsets[0];
  bed.style.setProperty("--offset", `${offset}px`);
  gameRender();
  $("#target").focus();
};
window.addEventListener("pagehide", () => {
  active = false;
  if (frame !== null) cancelAnimationFrame(frame);
  if (scrollFrame !== null) cancelAnimationFrame(scrollFrame);
});
window.addEventListener("pageshow", () => {
  active = true;
  sync();
  updateStory();
});
function resetSlots() {
  $("#prints").replaceChildren(
    ...Array.from({ length: 5 }, (_, i) => {
      const slot = document.createElement("li");
      slot.className = "slot";
      slot.innerHTML = `<div class="sheet"></div><span>第 ${i + 1} 张</span>`;
      return slot;
    }),
  );
  $("#press-note").textContent = "";
}
resetSlots();
sync();
updateStory();
gameRender();
