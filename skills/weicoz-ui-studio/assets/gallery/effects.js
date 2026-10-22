const $ = (selector) => document.querySelector(selector);
const reduced = matchMedia("(prefers-reduced-motion: reduce)");
let paused = false;
let frame = null;
let active = true;
let ticks = 0;
const dots = $("#dots");
const ctx = dots.getContext("2d");
let pointer = { x: -1000, y: -1000 };
dots.addEventListener("pointermove", (event) => {
  const box = dots.getBoundingClientRect();
  pointer = {
    x: ((event.clientX - box.left) / box.width) * dots.width,
    y: ((event.clientY - box.top) / box.height) * dots.height,
  };
});
dots.addEventListener("pointerleave", () => (pointer = { x: -1000, y: -1000 }));
const canvas = $("#shader");
let gl = null;
let program = null;
let timeUniform = null;
try {
  gl = canvas.getContext("webgl", {
    antialias: true,
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
    "attribute vec3 position; uniform float time; varying vec3 color; void main(){float a=time*.4+.5; float b=time*.25+.3; vec3 p=position; p.xz=mat2(cos(a),-sin(a),sin(a),cos(a))*p.xz; p.yz=mat2(cos(b),-sin(b),sin(b),cos(b))*p.yz; float depth=4.0+p.z; gl_Position=vec4(p.x*1.5,p.y*2.6,1.1*depth-2.2,depth);color=position*.25+vec3(.5,.65,.5);}",
  );
  const fragment = compile(
    gl.FRAGMENT_SHADER,
    "precision mediump float; varying vec3 color; void main(){gl_FragColor=vec4(color,1.0);}",
  );
  program = gl.createProgram();
  gl.attachShader(program, vertex);
  gl.attachShader(program, fragment);
  gl.linkProgram(program);
  gl.deleteShader(vertex);
  gl.deleteShader(fragment);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS))
    throw new Error("shader link failed");
  gl.useProgram(program);
  const vertices = [
    [-1, -1, -1],
    [1, -1, -1],
    [1, 1, -1],
    [-1, 1, -1],
    [-1, -1, 1],
    [1, -1, 1],
    [1, 1, 1],
    [-1, 1, 1],
  ];
  const faces = [
    0, 1, 2, 0, 2, 3, 4, 6, 5, 4, 7, 6, 0, 4, 5, 0, 5, 1, 3, 2, 6, 3, 6, 7, 0,
    3, 7, 0, 7, 4, 1, 5, 6, 1, 6, 2,
  ];
  const buffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(
    gl.ARRAY_BUFFER,
    new Float32Array(faces.flatMap((i) => vertices[i])),
    gl.STATIC_DRAW,
  );
  const location = gl.getAttribLocation(program, "position");
  gl.vertexAttribPointer(location, 3, gl.FLOAT, false, 0, 0);
  gl.enableVertexAttribArray(location);
  gl.enable(gl.DEPTH_TEST);
  timeUniform = gl.getUniformLocation(program, "time");
  $("#shader-status").textContent = "WebGL 已就绪 · 实时几何与着色器";
} catch {
  gl = null;
  canvas.classList.add("unavailable");
  $("#shader-status").textContent = "WebGL 不可用，显示静态色块替代。";
}
canvas.addEventListener("webglcontextlost", (event) => {
  event.preventDefault();
  gl = null;
  canvas.classList.add("unavailable");
  $("#shader-status").textContent = "绘图上下文已中断，显示静态替代。";
});
function draw() {
  if (ctx) {
    ctx.fillStyle = "#192d24";
    ctx.fillRect(0, 0, dots.width, dots.height);
    for (let row = 0; row < 8; row++) {
      for (let col = 0; col < 18; col++) {
        let x = 16 + col * 25,
          y = 15 + row * 25;
        const dx = x - pointer.x,
          dy = y - pointer.y;
        const distance = Math.hypot(dx, dy);
        if (!reduced.matches && distance < 85 && distance > 0) {
          x += (dx / distance) * (85 - distance) * 0.25;
          y += (dy / distance) * (85 - distance) * 0.25;
        }
        const wave = reduced.matches
          ? 0
          : Math.sin(ticks * 0.02 + col * 0.3 + row * 0.3) * 2;
        ctx.beginPath();
        ctx.arc(x, y + wave, 2, 0, Math.PI * 2);
        ctx.fillStyle = "#bbce9f";
        ctx.fill();
      }
    }
  }
  if (gl) {
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.clearColor(0.098, 0.176, 0.141, 1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    gl.uniform1f(timeUniform, ticks / 60);
    gl.drawArrays(gl.TRIANGLES, 0, 36);
  }
}
function loop() {
  frame = null;
  if (!active || paused || reduced.matches || document.hidden) return;
  ticks++;
  draw();
  frame = requestAnimationFrame(loop);
}
function sync() {
  if (frame !== null) {
    cancelAnimationFrame(frame);
    frame = null;
  }
  document.body.dataset.paused = String(paused || reduced.matches);
  document.body.dataset.reduced = String(reduced.matches);
  $("#motion-toggle").setAttribute("aria-pressed", String(paused));
  $("#motion-toggle").textContent = paused ? "恢复动态效果" : "暂停动态效果";
  $("#motion-status").textContent = reduced.matches
    ? "系统已开启减少动态效果，画面保持静态。"
    : paused
      ? "动态效果已暂停。"
      : "动态效果正在播放，可随时暂停。";
  draw();
  if (active && !paused && !reduced.matches && !document.hidden)
    frame = requestAnimationFrame(loop);
}
$("#motion-toggle").onclick = () => {
  paused = !paused;
  sync();
};
reduced.addEventListener("change", sync);
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
      (-box.top + innerHeight * 0.2) /
        Math.max(1, box.height - innerHeight * 0.5),
    ),
  );
  story.style.setProperty("--progress", progress);
  $("#story-progress").value = progress;
}
function queueStory() {
  if (scrollFrame === null) scrollFrame = requestAnimationFrame(updateStory);
}
window.addEventListener("scroll", queueStory, { passive: true });
window.addEventListener("resize", queueStory);
const targets = [
  [20, 50],
  [65, 30],
  [42, 70],
  [80, 55],
  [30, 25],
];
let score = 0;
let gamePaused = false;
function gameRender() {
  const done = score === 5;
  $("#target").disabled = done || gamePaused;
  $("#target").hidden = done;
  const [x, y] = targets[Math.min(score, 4)];
  $("#target").style.setProperty("--tx", `${x}%`);
  $("#target").style.setProperty("--ty", `${y}%`);
  $("#game-status").textContent = done
    ? "5 / 5，完成。休息一下吧。"
    : gamePaused
      ? `${score} / 5，练习已暂停。`
      : `${score} / 5，继续抓住下一束光。`;
  $("#game-pause").setAttribute("aria-pressed", String(gamePaused));
  $("#game-pause").textContent = gamePaused ? "继续练习" : "暂停练习";
}
$("#target").onclick = () => {
  if (!gamePaused && score < 5) {
    score++;
    gameRender();
    if (score === 5) $("#game-reset").focus();
  }
};
$("#game-pause").onclick = () => {
  gamePaused = !gamePaused;
  gameRender();
};
$("#game-reset").onclick = () => {
  score = 0;
  gamePaused = false;
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
sync();
updateStory();
gameRender();
