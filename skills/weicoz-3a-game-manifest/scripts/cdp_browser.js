#!/usr/bin/env node

/**
 * 轻量级 CDP (Chrome DevTools Protocol) 浏览器控制辅助脚本
 * 当 ego-browser 不存在或异常时，作为兜底渠道连接 Chrome 执行检索
 */

const http = require("http");
const { execSync } = require("child_process");

const CDP_PORT = process.env.CDP_PORT || 9222;

function checkCdpAlive() {
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:${CDP_PORT}/json/version`, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        try {
          resolve(JSON.parse(data));
        } catch {
          resolve(null);
        }
      });
    });
    req.on("error", () => resolve(null));
    req.setTimeout(2000, () => {
      req.destroy();
      resolve(null);
    });
  });
}

async function main() {
  const args = process.argv.slice(2);
  const action = args[0] || "check";
  const keyword = args[1] || "";

  const versionInfo = await checkCdpAlive();

  if (action === "check") {
    if (versionInfo) {
      console.log(JSON.stringify({ ok: true, msg: "CDP 服务已就绪", data: versionInfo }, null, 2));
    } else {
      console.log(JSON.stringify({ 
        ok: false, 
        msg: `CDP 端口 ${CDP_PORT} 未开放。若需使用 CDP 兜底，请使用如下命令启动 Chrome 调试实例：`,
        startCmd: `/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=${CDP_PORT} &`
      }, null, 2));
    }
    return;
  }

  if (!versionInfo) {
    console.error(`[CDP Error] 无法连接到 CDP 端口 ${CDP_PORT}，请确认 Chrome 调试实例已启动。`);
    process.exit(1);
  }

  console.log(`[CDP] 已连接到浏览器: ${versionInfo.Browser}, webSocketDebuggerUrl: ${versionInfo.webSocketDebuggerUrl}`);
}

main().catch(console.error);
