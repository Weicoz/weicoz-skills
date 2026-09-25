#!/usr/bin/env node

/**
 * 自动扫描 workspace/games/manifests/ 下各游戏目录并重新生成规范的 INDEX.md
 */

const fs = require("fs");
const path = require("path");

const MANIFESTS_DIR = process.env.MANIFESTS_DIR || 
  path.resolve(process.cwd(), "workspace/games/manifests") || 
  "/Users/weicoz/File/git/LLM-wiki/workspace/games/manifests";

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
    }

    games.push(meta);
  }

  let md = `# Steam 游戏入库清单与本体资源总索引\n\n`;
  md += `> 自动维护汇总 \`workspace/games/manifests/\` 目录下所有已归档的游戏入库清单与本体资源。  \n`;
  md += `> **规则**：清单文件（≤10MB）默认由 Skill 自动下载就绪；游戏完整本体（几G~几十G）由用户在需要时按链接手动下载。  \n`;
  md += `> 最后更新：${new Date().toISOString().split("T")[0]}\n\n`;
  md += `---\n\n`;
  md += `## 资源概况一览表\n\n`;
  md += `| AppID | 中文名 | 英文名 | 清单状态 (自动下载) | 完整本体 (用户手动下载) | 目录与详情 |\n`;
  md += `|---|---|---|---|---|---|\n`;

  for (const g of games) {
    const encodedDir = encodeURIComponent(g.dirName);
    const bodyCell = g.bodyUrl ? `[${g.bodySize} 网盘链接](${g.bodyUrl})` : (g.bodySize !== "-" ? g.bodySize : "暂无");
    md += `| \`${g.appId}\` | ${g.chineseName} | ${g.englishName} | ✅ ${g.manifestStatus} | ${bodyCell} | [📂 详情目录](./${encodedDir}/) |\n`;
  }

  md += `\n---\n\n## 各游戏详细概况\n\n`;

  for (const g of games) {
    const encodedDir = encodeURIComponent(g.dirName);
    md += `### [${g.appId}] ${g.chineseName} (${g.englishName})\n\n`;
    md += `- **Steam AppID**：\`${g.appId}\`\n`;
    md += `- **本地游戏目录**：[\`${g.dirName}/\`](./${encodedDir}/)\n`;
    md += `- **📌 清单状态**：${g.manifestStatus}，已就绪于目录中供 SteamTools 读取\n`;
    if (g.manifestUrl) {
      md += `  - 备用清单网盘：${g.manifestUrl}\n`;
    }
    if (g.bodyUrl) {
      md += `- **📦 完整本体 (用户手动下载)**：[下载链接](${g.bodyUrl}) (体积: ${g.bodySize}，解压即玩)\n`;
    }
    md += `\n`;
  }

  const indexPath = path.join(MANIFESTS_DIR, "INDEX.md");
  const readmeMirrorPath = path.join(MANIFESTS_DIR, "README.md");
  fs.writeFileSync(indexPath, md, "utf8");
  fs.writeFileSync(readmeMirrorPath, md, "utf8");
  console.log("Successfully refreshed INDEX.md & README.md for", games.length, "games.");
}

scanAndBuildIndex();
