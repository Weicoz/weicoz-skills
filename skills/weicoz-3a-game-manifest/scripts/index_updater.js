#!/usr/bin/env node

/**
 * 自动扫描 manifests/ 下各游戏目录并重新生成规范的 INDEX.md 和 README.md
 * 包含硬件配置推荐与预估运行画质/FPS (基于 i5-9600K / RTX 2060 6G / 16G RAM)
 */

const fs = require("fs");
const path = require("path");

const MANIFESTS_DIR = process.env.MANIFESTS_DIR || 
  (fs.existsSync(path.resolve(process.cwd(), "manifests")) ? path.resolve(process.cwd(), "manifests") : path.resolve(__dirname, "../manifests"));

const REPO_ROOT = path.resolve(MANIFESTS_DIR, "..");

function scanAndBuildIndex() {
  if (!fs.existsSync(MANIFESTS_DIR)) {
    console.error("Manifests dir not found:", MANIFESTS_DIR);
    process.exit(1);
  }

  const entries = fs.readdirSync(MANIFESTS_DIR, { withFileTypes: true });
  const gameDirs = entries
    .filter(e => e.isDirectory() && /^\d+/.test(e.name))
    .map(e => e.name);

  const games = [];

  for (const dirName of gameDirs) {
    const fullDirPath = path.join(MANIFESTS_DIR, dirName);
    const readmePath = path.join(fullDirPath, "README.md");
    let meta = {
      appId: dirName.split(" - ")[0] || "",
      englishName: "",
      chineseName: "",
      manifestStatus: "已自动下载 (.lua)",
      manifestSize: "未知",
      manifestUrl: "",
      bodySize: "-",
      bodyUrl: "",
      recommendedSetting: "1080p 中画质 (推荐)",
      estimatedFps: "50-60 FPS",
      perfDetails: "",
      dirName
    };

    const parts = dirName.split(" - ");
    if (parts.length >= 3) {
      meta.appId = parts[0];
      meta.englishName = parts[1];
      meta.chineseName = parts[2];
    }

    // 检查本地是否存在 .lua 文件
    const files = fs.readdirSync(fullDirPath);
    const luaFile = files.find(f => f.endsWith(".lua"));
    if (luaFile) {
      const st = fs.statSync(path.join(fullDirPath, luaFile));
      meta.manifestSize = `${st.size} B`;
      meta.manifestStatus = `已下载 (${meta.manifestSize})`;
    }

    if (fs.existsSync(readmePath)) {
      const content = fs.readFileSync(readmePath, "utf8");
      
      const secA = content.split("## 📦 选项 B")[0] || "";
      const secB = content.split("## 📦 选项 B")[1] || "";

      const mUrlMatch = secA.match(/https:\/\/pan\.(?:quark|baidu)\.(?:cn|com)\/s\/[a-zA-Z0-9_-]+/);
      if (mUrlMatch) meta.manifestUrl = mUrlMatch[0];

      // 本体解析
      const bSizeMatch = secB.match(/本体体积[：*|\s]*([0-9.]+\s*[BKMGTbkmgt]+)/);
      if (bSizeMatch) meta.bodySize = bSizeMatch[1];
      const bUrlMatch = secB.match(/https:\/\/pan\.(?:quark|baidu)\.(?:cn|com)\/s\/[a-zA-Z0-9_-]+/);
      if (bUrlMatch) meta.bodyUrl = bUrlMatch[0];

      // 硬件性能推荐解析
      const perfMatch = content.match(/## 🎮 硬件运行建议[\s\S]*?(?=\n## |$)/);
      if (perfMatch) {
        const perfText = perfMatch[0];
        const resMatch = perfText.match(/推荐画质[：*|\s]*([^\n]+)/);
        const fpsMatch = perfText.match(/预估帧率[：*|\s]*([^\n]+)/);
        if (resMatch) meta.recommendedSetting = resMatch[1].replace(/[*_`]/g, "").trim();
        if (fpsMatch) meta.estimatedFps = fpsMatch[1].replace(/[*_`]/g, "").trim();
        meta.perfDetails = perfText.trim();
      }
    }

    games.push(meta);
  }

  let md = `# Steam 游戏入库清单与本体资源总索引\n\n`;
  md += `> 自动维护汇总 \`manifests/\` 目录下所有已归档的游戏入库清单、本体网盘与硬件流畅运行指南。  \n`;
  md += `> **基准配置参考**：\`Intel i5-9600K / NVIDIA RTX 2060 6GB / 16GB RAM\`（参考 doesitrun.com 跑分模型与实测调优）。  \n`;
  md += `> 最后更新：${new Date().toISOString().split("T")[0]}\n\n`;
  md += `---\n\n`;
  md += `## 资源与硬件运行概况一览表\n\n`;
  md += `| AppID | 游戏中文名 | 英文名 | 清单状态 | 推荐画质 (i5 + RTX 2060) | 预估 FPS | 完整本体 (按需下载) | 目录详情 |\n`;
  md += `|---|---|---|---|---|---|---|---|\n`;

  for (const g of games) {
    const encodedDir = encodeURIComponent(g.dirName);
    const bodyCell = g.bodyUrl ? `[${g.bodySize} 网盘](${g.bodyUrl})` : (g.bodySize !== "-" ? g.bodySize : "暂无");
    md += `| \`${g.appId}\` | ${g.chineseName} | ${g.englishName} | ✅ ${g.manifestStatus} | **${g.recommendedSetting}** | \`${g.estimatedFps}\` | ${bodyCell} | [📂 详情](./manifests/${encodedDir}/) |\n`;
  }

  md += `\n---\n\n## 各游戏详细概况与配置指南\n\n`;

  for (const g of games) {
    const encodedDir = encodeURIComponent(g.dirName);
    md += `### [${g.appId}] ${g.chineseName} (${g.englishName})\n\n`;
    md += `- **Steam AppID**：\`${g.appId}\`\n`;
    md += `- **游戏归档目录**：[\`manifests/${g.dirName}/\`](./manifests/${encodedDir}/)\n`;
    md += `- **📌 清单状态**：${g.manifestStatus}，已就绪于目录中供 SteamTools / 入库工具读取\n`;
    if (g.manifestUrl) {
      md += `  - 备用清单网盘：${g.manifestUrl}\n`;
    }
    if (g.bodyUrl) {
      md += `- **📦 完整本体 (用户手动下载)**：[下载链接](${g.bodyUrl}) (体积: ${g.bodySize}，解压即玩)\n`;
    }
    md += `- **🎮 本机硬件 (i5-9600K / RTX 2060 6G / 16G RAM) 运行指南**：\n`;
    md += `  - **推荐画质**：${g.recommendedSetting}\n`;
    md += `  - **预估帧率**：${g.estimatedFps}\n`;
    md += `\n`;
  }

  const rootIndexPath = path.join(REPO_ROOT, "INDEX.md");
  const rootReadmePath = path.join(REPO_ROOT, "README.md");
  const manifestsIndexPath = path.join(MANIFESTS_DIR, "INDEX.md");
  const manifestsReadmePath = path.join(MANIFESTS_DIR, "README.md");

  fs.writeFileSync(rootIndexPath, md, "utf8");
  fs.writeFileSync(rootReadmePath, md, "utf8");
  fs.writeFileSync(manifestsIndexPath, md, "utf8");
  fs.writeFileSync(manifestsReadmePath, md, "utf8");
  console.log("Successfully refreshed INDEX.md & README.md with hardware benchmarks for", games.length, "games.");
}

scanAndBuildIndex();
