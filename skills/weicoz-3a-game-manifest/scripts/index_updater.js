#!/usr/bin/env node

/**
 * 自动扫描 manifests/ 下各游戏目录并重新生成规范的 INDEX.md 和 README.md
 * 包含硬件配置推荐与预估运行画质/FPS (支持环境变量 STEAM_SPECS_* / STEAM_HARDWARE_SPECS 与配置文件)
 */

const fs = require("fs");
const path = require("path");

const MANIFESTS_DIR = process.env.MANIFESTS_DIR || 
  (fs.existsSync(path.resolve(process.cwd(), "manifests")) ? path.resolve(process.cwd(), "manifests") : path.resolve(__dirname, "../manifests"));

const REPO_ROOT = path.resolve(MANIFESTS_DIR, "..");

function validateSpecs(specs, sourceName) {
  const issues = [];
  if (!specs || typeof specs !== 'object') {
    return {
      valid: false,
      issues: ['配置内容不是有效的 JSON 对象'],
      warnings: [],
      sourceName
    };
  }

  const requiredFields = [
    { key: 'cpu', label: 'CPU (处理器型号)', example: 'Intel Core i5-9600K' },
    { key: 'gpu', label: 'GPU (显卡完整型号及显存)', example: 'NVIDIA GeForce RTX 2060 6GB' },
    { key: 'ram', label: 'RAM (系统运行内存)', example: '16GB' }
  ];

  for (const f of requiredFields) {
    if (!specs[f.key] || typeof specs[f.key] !== 'string' || !specs[f.key].trim()) {
      issues.push(`缺少必填字段 "${f.key}" (${f.label})，示例: "${f.example}"`);
    }
  }

  const warnings = [];
  if (!specs.vram) {
    warnings.push('未提供 vram (独立显存容量，建议提供如 "6GB" 以便虚幻5防爆显存调优)');
  }
  if (!specs.resolution) {
    warnings.push('未提供 resolution (目标分辨率，默认将按 1080p 预估)');
  }

  return {
    valid: issues.length === 0,
    issues,
    warnings,
    sourceName
  };
}

function getHardwareSpecs() {
  let foundRaw = null;
  let sourceName = null;

  // 1. 优先读取仓库内的配置文件（.user_specs.json 或 user_specs.json）
  const repoCandidates = [
    { p: path.join(REPO_ROOT, ".user_specs.json"), name: "仓库本地配置文件 (.user_specs.json)" },
    { p: path.join(REPO_ROOT, "user_specs.json"), name: "仓库本地配置文件 (user_specs.json)" },
    { p: path.resolve(process.cwd(), ".user_specs.json"), name: "当前目录配置文件 (.user_specs.json)" },
    { p: path.resolve(process.cwd(), "user_specs.json"), name: "当前目录配置文件 (user_specs.json)" }
  ];
  for (const item of repoCandidates) {
    if (fs.existsSync(item.p)) {
      try {
        foundRaw = JSON.parse(fs.readFileSync(item.p, "utf8"));
        sourceName = item.name;
        break;
      } catch (e) {
        console.error(`⚠️ 读取配置文件 ${item.p} 解析 JSON 失败:`, e.message);
      }
    }
  }

  // 2. 其次读取环境变量：STEAM_HARDWARE_SPECS (JSON 字符串) 或 STEAM_SPECS_*
  if (!foundRaw) {
    if (process.env.STEAM_HARDWARE_SPECS) {
      try {
        foundRaw = JSON.parse(process.env.STEAM_HARDWARE_SPECS);
        sourceName = "系统环境变量 (STEAM_HARDWARE_SPECS)";
      } catch (e) {}
    } else if (process.env.STEAM_SPECS_CPU || process.env.STEAM_SPECS_GPU) {
      foundRaw = {
        cpu: process.env.STEAM_SPECS_CPU,
        gpu: process.env.STEAM_SPECS_GPU,
        ram: process.env.STEAM_SPECS_RAM,
        vram: process.env.STEAM_SPECS_VRAM,
        resolution: process.env.STEAM_SPECS_RESOLUTION,
        notes: process.env.STEAM_SPECS_NOTES
      };
      sourceName = "系统环境变量 (STEAM_SPECS_*)";
    }
  }

  // 3. 用户全局配置文件 (~/.config/steam-manifests/user_specs.json)
  if (!foundRaw) {
    const homeConfig = path.join(process.env.HOME || "", ".config/steam-manifests/user_specs.json");
    if (fs.existsSync(homeConfig)) {
      try {
        foundRaw = JSON.parse(fs.readFileSync(homeConfig, "utf8"));
        sourceName = "全局配置文件 (~/.config/steam-manifests/user_specs.json)";
      } catch (e) {}
    }
  }

  // 校验检查与提示用户补充
  if (!foundRaw) {
    console.warn("\n=======================================================");
    console.warn("⚠️  【硬件配置缺失】未检测到任何有效的硬件配置来源！");
    console.warn("👉  请补充硬件配置：在仓库根目录创建 .user_specs.json 或设置环境变量。");
    console.warn("   必填项：cpu (处理器), gpu (显卡及显存), ram (内存容量)");
    console.warn("   参考模板：user_specs.example.json");
    console.warn("=======================================================\n");
    return {
      cpu: "未配置CPU",
      gpu: "未配置显卡",
      ram: "未配置内存",
      vram: "-",
      resolution: "1080p",
      notes: "⚠️ 未配置硬件，请补充 .user_specs.json"
    };
  }

  const check = validateSpecs(foundRaw, sourceName);
  if (!check.valid) {
    console.warn("\n=======================================================");
    console.warn(`⚠️  【硬件配置字段不匹配】已检测到【${sourceName}】，但必填字段不全：`);
    for (const issue of check.issues) {
      console.warn(`   ❌ ${issue}`);
    }
    console.warn("👉  请补充缺失字段以获得准确的画质与帧率预测！");
    console.warn("=======================================================\n");
  } else {
    console.log(`✅ 【硬件配置校验匹配成功】`);
    console.log(`   来源: ${sourceName}`);
    console.log(`   CPU:  ${foundRaw.cpu}`);
    console.log(`   GPU:  ${foundRaw.gpu}`);
    console.log(`   RAM:  ${foundRaw.ram}`);
    if (foundRaw.vram) console.log(`   显存: ${foundRaw.vram}`);
    if (foundRaw.resolution) console.log(`   基准分辨率: ${foundRaw.resolution}`);
    if (check.warnings.length > 0) {
      for (const w of check.warnings) {
        console.log(`   💡 建议: ${w}`);
      }
    }
  }

  return {
    cpu: foundRaw.cpu || "未配置CPU",
    gpu: foundRaw.gpu || "未配置显卡",
    ram: foundRaw.ram || "未配置内存",
    vram: foundRaw.vram || "-",
    resolution: foundRaw.resolution || "1080p",
    notes: foundRaw.notes || ""
  };
}

function scanAndBuildIndex() {
  if (!fs.existsSync(MANIFESTS_DIR)) {
    console.error("Manifests dir not found:", MANIFESTS_DIR);
    process.exit(1);
  }

  const specs = getHardwareSpecs();
  const specSummary = `${specs.cpu} / ${specs.gpu} / ${specs.ram} RAM`;

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
  md += `> **基准配置参考**：\`${specSummary}\`（参考 doesitrun.com 跑分模型与实测调优）。  \n`;
  md += `> 最后更新：${new Date().toISOString().split("T")[0]}\n\n`;
  md += `---\n\n`;
  md += `## 资源与硬件运行概况一览表\n\n`;
  md += `| AppID | 游戏中文名 | 英文名 | 清单状态 | 推荐画质 (${specs.resolution || "1080p"}) | 预估 FPS | 完整本体 (按需下载) | 目录详情 |\n`;
  md += `|---|---|---|---|---|---|---|---|\n`;

  for (const g of games) {
    const encodedDir = encodeURIComponent(g.dirName);
    const bodyCell = g.bodyUrl ? `[${g.bodySize} 网盘](${g.bodyUrl})` : (g.bodySize !== "-" ? g.bodySize : "暂无");
    md += `| \`${g.appId}\` | ${g.chineseName} | ${g.englishName} | ✅ ${g.manifestStatus} | **${g.recommendedSetting}** | \`${g.estimatedFps}\` | ${bodyCell} | [📂 详情](./manifests/${encodedDir}/) |\n`;
  }

  md += `\n---\n\n## ⚙️ 硬件配置文件规范 (.user_specs.json / user_specs.json)\n\n`;
  md += `本仓库基于硬件基准配置，结合 \`doesitrun.com\` 跑分模型与游戏引擎特性（UE5 / Northlight / RE Engine 等），为全库游戏提供定制化的**流畅运行画质推荐、预估帧率与避坑指南**。\n\n`;
  md += `### 1. 配置文件放置路径与读取优先级\n\n`;
  md += `工具按以下优先级自动识别硬件基准配置：\n\n`;
  md += `1. **仓库本地配置文件（最高优先）**：\`steam-manifests/.user_specs.json\` 或 \`user_specs.json\`\n`;
  md += `2. **系统环境变量**：\`STEAM_SPECS_CPU\`, \`STEAM_SPECS_GPU\`, \`STEAM_SPECS_RAM\`, \`STEAM_SPECS_VRAM\`, \`STEAM_SPECS_RESOLUTION\` 或 \`STEAM_HARDWARE_SPECS\`\n`;
  md += `3. **用户全局配置文件**：\`~/.config/steam-manifests/user_specs.json\`\n\n`;
  md += `> **隐私与 Git 隔离提示**：\`.user_specs.json\` 默认已加入 \`.gitignore\`，若无需公开个人硬件信息可直接放置该隐藏文件；如需作为公开基准，可直接提交 \`user_specs.json\`（仓库已提供模板 \`user_specs.example.json\`）。\n\n`;
  md += `### 2. 字段规范要求\n\n`;
  md += `| 字段名 | 类型 | 必需 | 说明与示例 |\n`;
  md += `|---|---|---|---|\n`;
  md += `| \`cpu\` | string | **必填** | 处理器型号，例如 \`"Intel Core i5-9600K"\` 或 \`"AMD Ryzen 5 5600X"\` |\n`;
  md += `| \`gpu\` | string | **必填** | 显卡完整型号及显存容量，例如 \`"NVIDIA GeForce RTX 2060 6GB"\` |\n`;
  md += `| \`ram\` | string | **必填** | 系统运行内存大小，例如 \`"16GB"\` 或 \`"32GB"\` |\n`;
  md += `| \`vram\` | string | 建议 | 独立显存容量，例如 \`"6GB"\`（用于大作与虚幻5防爆显存专项调优） |\n`;
  md += `| \`resolution\` | string | 建议 | 目标基准分辨率，默认为 \`"1080p"\`（可选 \`"1080p"\`、\`"1440p"\`、\`"4K"\` 等） |\n`;
  md += `| \`notes\` | string | 可选 | 硬件特殊属性或调优备忘，例如 \`"6核6线程无超线程，Turing架构6G显存，支持DLSS 2，大作建议关光追控制纹理"\` |\n\n`;
  md += `### 3. 配置示例模板 (\`.user_specs.json\`)\n\n`;
  md += `\`\`\`json\n`;
  md += `{\n`;
  md += `  "cpu": "Intel Core i5-9600K",\n`;
  md += `  "gpu": "NVIDIA GeForce RTX 2060 6GB",\n`;
  md += `  "ram": "16GB",\n`;
  md += `  "vram": "6GB",\n`;
  md += `  "resolution": "1080p",\n`;
  md += `  "notes": "6核6线程无超线程，Turing架构6G显存，支持DLSS 2，大作建议关光追控制纹理"\n`;
  md += `}\n`;
  md += `\`\`\`\n\n`;
  md += `### 4. 刷新索引与调优指南命令\n\n`;
  md += `修改配置文件或添加新游戏后，在仓库根目录执行以下命令，即可全自动依据最新配置刷新全库指南与总表：\n\n`;
  md += `\`\`\`bash\n`;
  md += `node scripts/index_updater.js\n`;
  md += `\`\`\`\n\n`;
  md += `---\n\n## 各游戏详细概况与配置指南\n\n`;

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
    md += `- **🎮 本机硬件 (${specSummary}) 运行指南**：\n`;
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

if (process.argv.includes("--check")) {
  const specs = getHardwareSpecs();
  process.exit(0);
}

scanAndBuildIndex();
