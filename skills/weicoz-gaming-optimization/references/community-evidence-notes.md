> 历史资料快照：2026-11-08。以下是当时的研究记录，软件版本、支持范围和个人案例状态不得直接当作当前事实。使用前按具体问题复核一手来源。

# 案例主机 游戏优化：社区经验与争议核验资料单

读取日期：2026-11-08。只读资料调研；未访问或修改 案例主机，未安装软件，未跑游戏实测。

## 可直接用于主报告的判断

1. **先提高和稳定基础帧率，再讨论插帧。** Lossless Scaling 的作者明确要求保留 GPU 余量，否则会拖低游戏本身的帧率。不能把插帧后显示的 FPS 当作同等基础帧率、交互频率或端到端延迟。
2. **双显卡 LSFG 是有条件的工程方案。** 社区有带 OSLTT 的延迟测量与配置指南，证明该路径值得试验；它不支持“任何副卡都无代价”“买张亮机卡即可”的结论。PCIe 线路、显示器接在哪张卡、第二张卡的算力、供电与空间必须逐项核对。
3. **OptiScaler 的首要价值是替换/接入特定超分与帧生成路径。** 支持列表是逐游戏兼容经验，不是所有 GPU 全功能通用保证。项目作者明确警告不得用于在线游戏；它也明确没有官方网站或官方管理器，下载来源必须从主仓确认。
4. **“显存快满”只是线索，不能单凭一个数字确诊爆显存。** Windows 给进程的可用显存预算不等于显卡标称容量；超过预算可造成卡顿。必须结合帧时间、纹理/光追/分辨率的单变量试验核验。
5. **着色器编译卡顿与稳定的 GPU 性能不足是两类问题。** 前者常发生在首次进入场景或出现新材质时；玩家调画质无法保证修复开发者漏掉的 PSO。清着色器缓存是特定故障处理，会触发重编译，不能每次开游戏前都清。
6. **禁用 HPET、修改 BCD 计时器、常驻清内存没有本机可靠证据。** 微软把相关 BCD 开关定义为调试用途；系统会自行选计时源，待机内存也会被系统回收。不能把这些手段列为通用“必做优化”。

## 证据分级

- A：产品作者、引擎作者、操作系统文档直接定义的行为。
- B：作者自己发布的社区实验，给出部分硬件、场景或测量方法，但未由本次调研复跑。
- C：个人体感、评论、缺原始数据，作为故障线索。
- 所有收益都未在 案例主机 上验证。未给出其 CPU、GPU、内存、屏幕与游戏清单时，不给对应 FPS 预测或采购型号。

## 1. Lossless Scaling 作者说明：兼容广，但要付算力成本

来源：[Lossless Scaling Steam 商店页](https://store.steampowered.com/app/993090/Lossless_Scaling/)，THS 作者/发行商；A。

已读取 About This Software、Dual GPU Support、Compatibility with Online Games、Requirements。作者明确描述：LSFG 生成附加帧；缩放通过降低原始分辨率，再以算法恢复部分观感；支持把计算交给第二张 GPU；需要 GPU 余量，否则影响游戏原始帧率。常规支持窗口/无边框模式；独占全屏有特定第二显示输出例外。

作者对反作弊的措辞是社区认为可用，但不能保证。由此得出的决策：普通单机可以按游戏做 A/B 试验；有重要账号与明确禁止外部工具的在线游戏，先看该游戏规则，不能写“绝不封号”。该路径与直接替换游戏 DLL 的 mod 必须分开讨论。

未确认：案例主机 当前是否已经购买该软件、版本、捕获 API 与游戏覆盖层兼容情况。

## 2. 双 GPU 原始社区指南：有测量条件，不能搬运宣传结论

来源：[RavengerPVP 原始 Reddit 指南](https://www.reddit.com/r/losslessscaling/comments/1jtaoau/official_dual_gpu_overview_guide/)，B；[可读转载页](https://sageinfinity.github.io/docs/Guides/DualGPUGuide)；[Steam 置顶入口](https://steamcommunity.com/app/993090/discussions/0/594016978256007124/)。后两者与原帖不是三个独立实验。

指南自称来自多台系统测试，给出的延迟图说明：使用 OSLTT；LSFG 为 X4；Reflex 与 G-SYNC 开启；基础帧率固定 60；每次显示器连接到执行帧生成的显卡。文中展示的双卡示例是 RTX 4060 Ti 16GB 与 Arc B570。

该流程是主卡渲染 → PCIe 复制 → 副卡插帧 → 副卡输出。指南估计复制额外延迟约 3–5 ms；这是作者样本值，不能写成硬件定律。若显示器仍插在主卡，插帧后的帧还要回传，增加带宽与内存控制器负担。指南要求两槽真实线路足够，物理 x16 不代表电气 x16；副卡算力不足同样成为瓶颈。指南列举的分辨率/FPS 上限仅为经验表。

**可采纳**：用户手上已有空闲副卡，且主板/电源/显示链路满足时，把双卡方案列为后置试验。

**不得直接采纳**：宣称它普遍低于 DLSS/FSR 延迟；为本机未核验的 PCIe 拓扑承诺零损耗；仅为插帧立即采购副卡。原始测试未由本次复跑，图表未完整提取原始 CSV。

## 3. 插帧实测中的指标误读：Presented 与 Displayed 必须分开

来源：[AFG 帧时间社区实验与评论](https://www.reddit.com/r/losslessscaling/comments/1qg7etr/afg_frame_pacing_video_showcase_of_adaptive_fg/)，B/C。

作者用《赛博朋克 2077》两个场景展示自适应插帧，提供了 9070 XT 渲染 + 6700 XT 辅助、144 Hz 输出、AFG 136 FPS、DXGI、Queue target 1 等配置。评论者 CptTombstone 指出，应用提交帧间隔与显示变化间隔能产生不同判断，特别是插帧、flip metering 情况；原作者随后说明其启用了显示指标，并补图。这是一条有价值的方法学纠错记录，不能作为“AFG 在所有游戏顺滑”的证明。

同帖另一名用 RTX 4060 执行插帧的用户报告低于 2 倍的自适应插帧在部分游戏有平移顿挫，固定 X2 对其更好。这是 C 级反例，未提供完整重复实验，适合提示“固定倍数与自适应要逐游戏比较”，不适合推出普遍禁用自适应。

一手定义依据：[PresentMon Capture Application README](https://github.com/GameTechDev/PresentMon/blob/main/README-CaptureApplication.md)，A。README 分别定义 Presented FPS、Displayed FPS、GPU Busy、Displayed Time 与 Frame Type；并把 Display Latency 定义为提交到扫描输出的时间。由此推断：该指标不能直接等同鼠标按下到屏幕变化的总延迟。监控工具能否识别某种 FG、是否监控到了 LS 输出进程，也必须先验证。

## 4. OptiScaler：真实功能、兼容边界、下载来源

来源：[OptiScaler 主仓 README](https://github.com/OptiScaler/OptiScaler)，A。

项目定位是替换已支持 DLSS2+/FSR2+/XeSS 游戏的超分路径，并管理帧生成。实验性 OptiFG 仅支持 DX12，HUD 残影与 HUDfix 是明确边界；DX11/DX12/Vulkan 的功能集合不同。README 明确警告在线游戏会触发反作弊并导致封禁。

README 还明确：没有官方网站、没有官方管理器；可信来源是该 GitHub、其 Discord、Nitec 的 NexusMods 页面，软件免费。因此网上自称官网的 optiscaler.* 页面和收费“一键包”不能仅凭名字采信。搜索中确有自称 OptiScaler 官网的站点，本资料单不以其为依据。

来源：[作者维护的社区兼容表](https://github.com/OptiScaler/OptiScaler/wiki/Compatibility-list)，A/B。读取时页面显示 2026-11-06 编辑，表格自身标注更新 2026-11-02；它要求提交游戏名、输入路径、说明与 Opti 覆盖层截图。它是社区已试配置集合，并自述非完整列表。兼容勾选不代表当前驱动、最新补丁、任意后端与其他 mod 组合均通过。

报告建议：先用游戏原生超分/帧生成；只有画质/兼容确有不足时，再给离线单机单独建 mod 档案、记录文件、保留回退。不要把 mod 注入到在线客户端，也不要为了运行它关闭整机安全机制。

## 5. 显存预算：诊断纹理/光追/插帧引发的卡顿

来源：[微软 DXGI_QUERY_VIDEO_MEMORY_INFO](https://learn.microsoft.com/en-us/windows/win32/api/dxgi1_4/ns-dxgi1_4-dxgi_query_video_memory_info)，A。

文档定义 Budget 为操作系统给应用的显存预算；当 CurrentUsage 超过 Budget，会因系统公平分配显存的后台活动出现卡顿或性能损失。标称 8GB/12GB 不等于游戏独占同样容量，单看显存占用接近上限也不能区分资源缓存与实际超预算。

本次推断：若平均帧率尚可但转镜头/换场景有长帧，可以依次测试降低纹理、关闭高显存光追、降低分辨率/渲染目标、关闭插帧中的一个变量；看帧时间和画面贴图是否同步改善。系统内存不是等速显存扩容，不能用“共享显存很多”来保证高纹理安全。

未确认：本机是否超预算、游戏实际驻留/分配情况；需要本机记录与单变量复测。

## 6. 着色器编译：为什么降画质和插帧救不了所有卡顿

来源：[Unreal Engine 引擎工程师技术文章](https://www.unrealengine.com/tech-blog/game-engines-and-shader-stuttering-unreal-engines-solution-to-the-problem)，2025-02-04，A。

文章解释运行时首次需要 shader/PSO 而编译尚未完成时，渲染等待可形成长帧；不同 GPU 架构需要对应机器码。PSO 预缓存、加载期编译等主要由游戏开发者实现，漏收集、过晚编译仍有边界。修改画质也会改变所需 shader/PSO 集合。

玩家可采纳的推断：让游戏提供的编译阶段完成；在更新游戏/驱动之后区分首次冷跑与后续暖跑；用同一路线复测，不能把第一次遇到材质的额外编译算进某项画质开关的稳定成本。不能声称注入通用 Engine.ini 能保证解决所有 UE 卡顿。

来源：[Fortnite 官方 DX12 卡顿故障页](https://www.epicgames.com/help/c-34254770/c-38015632/a11302262?lang=en-US)，A。

官方描述了重复无休止编译这一特定故障，可通过清 cache 处理，同时明确首场仍会因重新编译而卡顿。因此“清 cache”有特定适用场景，不支持每天清空缓存来提帧的常规方案。官方页面在 NVIDIA 路径步骤上有重复，报告不机械复制其全部删除步骤。

## 7. HPET/BCD/计时器：把系统调试开关当通用优化，证据不足

来源：[微软 BCDEdit /set](https://learn.microsoft.com/en-us/windows-hardware/drivers/devtest/bcdedit--set)，A。

`useplatformclock` 强制 platform clock 充当系统性能计数器；微软注明仅供调试。`tscsyncpolicy` 同样是调试配置。该文档没有给出任何通用游戏增益承诺。

来源：[微软高精度时间戳说明](https://learn.microsoft.com/en-us/windows/win32/sysinfo/acquiring-high-resolution-time-stamps)，A。Windows 在合适硬件上用低开销 TSC 实现 QPC；不适合 TSC 的系统自动选 platform counter。QPC、应用等待计时器分辨率、BIOS HPET 设置是不同层面，不能把“Timer Resolution 调到 0.5ms”直接等同输入延迟降低同样数值。

结论：不把禁用 HPET、`useplatformtick`、`disabledynamictick` 或复制陌生 BCD 清单列为本机第一轮优化。若过去改过，先记当前值与原始目的，再以可恢复方式比较默认配置。这里不宣称这些设置绝无特定兼容用途；现有证据只不足以支持通用收益。

## 8. 清待机内存：可作故障工具，不是“空闲 RAM 越多越快”

来源：[微软性能团队：Mystery Memory Leak](https://techcommunity.microsoft.com/blog/askperf/mystery-memory-leak-where-did-my-memory-go/1675369)，A。Standby 是当前不活跃但仍缓存于物理 RAM 的页面，系统需要时优先再利用。RAMMap 的排查用途是解释异常内存归属；该文也提到特定内存泄漏时可以清区域暂时处理，没有承诺游戏加速。

来源：[微软 Working Set](https://learn.microsoft.com/en-us/windows/win32/memory/working-set)，A。进程访问不在其工作集的可分页页会触发缺页；软缺页不等于磁盘读取，硬缺页需要后备存储。工作集清空与清 standby 也不是同一操作。

本次推断：不为本机默认装常驻清内存软件。若有异常内存持续上涨、硬缺页或后台占用，先定位对应进程/驱动/游戏与提交量，再处理。显示空闲内存上涨不能作为性能提升证据。

## 9. 给主报告的最小可重复验证方案（分析建议，未执行）

1. 记录游戏版本、驱动、系统、分辨率、屏幕刷新率与连接口；记录全部画质设置。关闭帧生成，拿到基础性能。
2. 选择可重复 60–120 秒路线，包含最吃配置的战斗/城市场景；先暖机/暖缓存，再各做至少 3 次。以结果离散度判断小幅变化是否只是噪声。
3. 同时记录平均 FPS、定义一致的 1% low、帧时间曲线/长帧次数、GPU Busy 与温度功耗。总 CPU 占用低不能排除单线程或同步瓶颈；GPU 占用低也要先排除限帧/VSync/加载等待。
4. 对纹理、阴影、体积效果、光追、超分档位逐一改变。先在动态游玩中看画质，再记录性能；避免仅在静止截图评判时域超分。
5. 比较原生 FG、驱动 FG、LSFG 时分别保留基础帧率与显示帧率。对话框/UI/字幕、粒子、头发、细线、快速横移、鼠标准星和转角做伪影检查。判断输入响应时不可拿显示 FPS 替代端到端延迟。
6. 用真实显示输出过程核验监控对象。若软件延迟指标不可用，就标未验证；有高速摄影/OSLTT/LDAT 才报告对应测量定义下的绝对输入延迟。
7. 保留设置只在“画质可接受 + 基础帧率/长帧/体感至少一项改善且其余无实质退化”的条件下；其余回退。单次多 3 FPS 不写成稳定收益。

## 未完成与风险

未复跑任何社区 CSV 或硬件延迟实验；未完整观看社区帖嵌入的视频，文字与测量方法已读取。
社区双卡指南、mod 兼容表与软件版本会更新；落地时按本机具体游戏补丁、反作弊规则与主板手册复核。
