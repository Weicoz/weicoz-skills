> 历史资料快照：2026-11-08。以下是当时的研究记录，软件版本、支持范围和个人案例状态不得直接当作当前事实。使用前按具体问题复核一手来源。

# 案例主机 游戏优化：官方技术依据核查

## 补充：主机插帧与串流捕获的区别（2026-11-08）

- [Lossless Scaling开发者2.6.0发布说明](https://steamcommunity.com/app/993090/discussions/0/4209246056405471570/)明确记录DXGI模式下LS窗口无法被其他程序捕获的限制。同帖有WGC成功串流的个人案例；它不是当前所有版本的兼容保证。
- [Sunshine原始issue #3621](https://github.com/LizardByte/Sunshine/issues/3621)报告某些DLSS FG DLL版本只能在客户端收到真实帧，另有评论称FSR3在其环境正常。记录支持按具体算法/版本/捕获路径判断，不支持“所有插帧都能传”或“所有插帧都不能传”。
- 当前项目决定：剔除主机LSFG；原生FG先关，待独立确认客户端实际收益才纳入。先前泛化的本地试验建议，不代表当前串流计划。
- 未运行任何修复工具、修改MPO/DWM、重启串流服务或复现上述历史问题。

读取日期：2026-11-08。资料范围：已实际打开并读取的厂商、游戏开发商、工具维护者一手资料。未访问或改动 案例主机；本文件不包含该机实测。

## 可直接进入总报告的结论

1. **先救真实渲染帧率，再考虑插帧。** 超分减少渲染像素，帧生成增加显示中间帧。两者解决的问题不同；“显示120 FPS”不能替代游戏真实更新速度、输入响应和帧时间检查。[S1][S2][S12]
2. **先选游戏原生集成，再试驱动级或外部方案。** DLSS/FSR/XeSS原生实现能取得运动矢量、深度等信息；驱动/外部方案更通用，但最终仍需逐游戏检查UI、遮挡、快速运动与延迟。此排序是根据接口和兼容条件作出的工程建议，并非各算法每场景画质排名。[S1][S2][S3][S6][S7]
3. **FSR3的官方推荐门槛是插帧前约60 FPS，低于30 FPS明确避免。** 40→80只表明显示帧数增加，无法推导出原生80 FPS手感；Intel旧XeSS-FG指南另列最低40、推荐60，不得把不同算法的门槛混成一个强制值。[S2][S3]
4. **不得把优化开关全开。** Nixxes明确不推荐FSR FG叠AFMF；对其游戏，旧版驱动Anti-Lag会影响帧节奏，游戏内Anti-Lag2按支持情况使用。其他游戏必须按自身说明与实测决定。[S8]
5. **安全设置不列入默认提速清单。** VBS/HVCI保护内核；老CPU的性能负担更大，但不能从这一点推出该机必须关闭。先记录真实瓶颈与游戏反作弊要求。[S11]
6. **旧视频的“适用硬件”必须刷新。** XeSS2.1已开放兼容非Intel显卡，Smooth Motion已支持RTX40；2026年官方FSR页面也已扩大ML超分支持。旧结论只适用于当时版本。[S4][S6][S14]

## S1 NVIDIA DLSS：功能和硬件必须拆开

- 来源：[NVIDIA DLSS Developer](https://developer.nvidia.com/rtx/dlss)；[官方DLSS4 FAQ](https://forums.developer.nvidia.com/t/dlss-4-faq/321939)。证据等级：A，厂商产品文档及官方员工FAQ；已读取。
- 当前开发者页标注DLSS4.5、第二代Transformer和Dynamic/6X MFG，页脚更新时间为2026年10月。页面说最多每个渲染帧生成5个额外帧，不能写成游戏逻辑更新6倍。
- 官方FAQ列：Super Resolution、Ray Reconstruction、DLAA支持所有GeForce RTX；普通Frame Generation支持RTX40/50；Multi Frame Generation支持RTX50。GTX不能因NVIDIA品牌而使用DLSS超分。
- Super Resolution从低分辨率输入、多帧历史和运动数据重建高分辨率图像；DLAA按原生分辨率抗锯齿，因此DLAA不属于“降低内部渲染分辨率提速”方案。
- 未确认：具体游戏已集成何版本、驱动覆盖是否允许该游戏、实际GPU型号。确认方法：游戏版本和设置、官方游戏支持列表、NVIDIA App程序配置；不凭“DLSS4”标签推断所有子功能可用。

## S2 AMD GPUOpen FSR3：原生帧率、VRR与叠加层

- 来源：[AMD GPUOpen FSR3](https://gpuopen.com/fidelityfx-super-resolution-3/)。证据等级：A，算法提供者开发文档；已读取。
- 官方建议插帧前最低60 FPS获得最佳效果；低于60时插值瑕疵更突出，低于30应避免。超分已有的瑕疵还会延续到生成帧。
- FSR3.1允许帧生成搭配其他超分；这不表示所有游戏的菜单都提供该组合。
- 官方表格区分VRR及VSync组合：稳定帧时间可用VRR+VSync；无VRR且帧率不足时，同步间隔会造成顿挫。不得照搬AFMF的“VSync必须关”到原生FSR FG。
- DXGI拦截和第三方OSD可损害帧节奏，AMD建议禁用有冲突的叠加层；不是要求停止一切监控。记录时可先选兼容工具或无OSD抓取。
- 未确认：该机的生成帧、VRR、叠加层是否兼容。方法：同场景逐项A/B；先关其他帧生成和叠加层，确认输出帧时间再逐项恢复。

## S3 Intel XeSS-FG：门槛与引擎输入

- 来源：[Intel XeSS Frame Generation Developer Guide](https://www.intel.com/content/www/us/en/developer/articles/technical/xess-fg-developer-guide.html)。证据等级：A，厂商开发文档；已读取。
- 文档写最低40 FPS、推荐60 FPS；基础输入可以是XeSS-SR后或原生渲染帧率。
- 原生集成需要运动矢量、深度缓冲和帧常量，XeLL集成是前提；DX12接口。
- 此网页仍写Arc/XMX独占，是旧版要求。新硬件兼容结论须接着看S4，不单独引用该页的硬件列表。
- 未确认：某游戏使用旧XeSS2还是新SDK、是否真的接入XeSS FG。方法：游戏发行说明、SDK/游戏内功能选项；有XeSS超分不等于有XeSS FG。

## S4 Intel官方GitHub：XeSS2.1跨厂商、XeSS3多帧

- 来源：[XeSS SDK2.1.0 Release](https://github.com/intel/xess/releases/tag/v2.1.0)；[XeSS SDK3.0.0 Release](https://github.com/intel/xess/releases/tag/v3.0.0)；[Releases当前列表](https://github.com/intel/xess/releases)。证据等级：A，厂商代码仓库发行说明；已读取。
- 2.1.0明确引入非Intel GPU的XeSS FG+Xe Low Latency，要求Shader Model6.4；非Intel上不支持独立使用XeLL。
- 3.0.0增加Intel Arc的3X/4X MFG，并改进所有支持GPU上的生成模型UI平滑性。当前列表最新SDK3.0.2，修正非Intel GPU XeLL内存泄漏和Streamline兼容问题。
- 判断：不得写“XeSS FG只支持Intel”；也不得反向写成“所有显卡支持XeSS3 MFG”。SDK发布不证明某款游戏已更新集成。
- 未确认：实际显卡驱动/Shader Model及游戏支持。方法：dxdiag、厂商驱动说明、游戏补丁；本轮没有在案例主机验证。

## S5 AMD AFMF2.1：支持范围、全屏模式和VSync

- 来源：[AMD Fluid Motion Frames](https://www.amd.com/en/products/software/adrenalin/afmf.html)。证据等级：A，厂商功能与要求页；已读取。
- 手动开启范围RX6000及更新；HYPR-RX入口主要RX7000及更新。RX6000仅支持独占全屏，RX7000及符合要求的700M等支持无边框；部分7000系列APU不在范围。
- 要求Adrenalin25.3.1+，游戏内和驱动VSync均关闭；推荐FreeSync。支持DX11/12、Vulkan、OpenGL。
- HYPR-RX会同时启用多项功能，宣传对比也可能叠FSR；不能把总提升归因于AFMF单项。
- 建议：先按单个游戏开启AFMF，记录基础帧率、显示帧率、帧时间和快速转向画面。全局开会把同一策略施加到不适合的游戏。
- 未确认：驱动具体版本、API/全屏实际生效状态。方法：Adrenalin该游戏状态和性能叠加层回读。

## S6 NVIDIA Smooth Motion：已支持RTX40，不能扩大到RTX30

- 来源：[Enabling Smooth Motion in NVIDIA App](https://nvidia.custhelp.com/app/answers/detail/a_id/5621/kw/platform)。证据等级：A，NVIDIA官方客服；页面更新2025-09-05，已读取。
- 当前官方支持RTX40和RTX50；选兼容DX11、DX12或Vulkan游戏，在NVIDIA App的Graphics→Program settings→Driver Settings开启。
- 算法在两个渲染帧之间推断额外帧；可以配原生分辨率或超分，主要覆盖没有DLSS FG的游戏。
- 判断：RTX30非官方支持范围。网上MOD、隐藏标志和硬件绕过不等同厂商支持，本轮不把它们列为默认方案。
- 未确认：具体游戏是否在兼容范围、实际驱动是否提供该开关。方法：按程序检查设置与官方驱动要求，再做A/B。

## S7 Lossless Scaling：通用性、GPU余量与反作弊边界

- 来源：[Lossless Scaling Steam官方商店](https://store.steampowered.com/app/993090/Lossless_Scaling/)。证据等级：A，开发商发布页；已读取。
- LSFG3生成中间帧；Fixed按倍数，Adaptive按目标显示帧率。缩放功能可独立使用。
- 官方要求窗口/无边框；独占全屏仅在特定第二显示器输出情形工作。需预留GPU资源，否则会降低游戏原始帧率。
- 最低Windows10 2004、现代核显、DX11；推荐Windows11 24H2、RTX30/RX6000/Arc。最低能启动不等于插帧体验合格。
- 商店称社区在部分反作弊游戏中未见问题，但开发商明确不保证安全。不得承诺“不会封号”。
- 未确认：特定游戏/反作弊授权、捕获模式、显示器和双GPU传输开销。方法：看游戏规则、开发者说明；先离线单机试用，不擅自购买或安装。

## S8 Nixxes：FSR FG不要叠AFMF，Anti-Lag分版本

- 来源：[Recommendations for AMD FSR frame generation](https://support.nixxes.com/hc/en-us/articles/48432066471827-Recommendations-for-AMD-FSR-frame-generation)。证据等级：A，实际PC移植开发商；更新2026-02-27，已读取。
- 要求优先调画质、分辨率、超分模式，使帧生成前约60 FPS；支持FreeSync则开启。
- 明确不推荐FSR3.1/4/Redstone FG叠AFMF。旧驱动Radeon Anti-Lag应关闭以免帧节奏/卡顿，支持的游戏内Anti-Lag2可以启用。
- 其FSR3 FG列表：RX5000+/RTX20+支持，RX6000+/RTX30+推荐；其他硬件即便能运行也可能没有收益。
- 判断：这是一手且可操作的游戏支持说明；不得把“Anti-Lag关”扩成全游戏、全版本永久禁用。
- 未确认：案例主机常玩游戏是否属于这些移植作品。方法：游戏清单及各游戏支持页。

## S9 DLSS FG与HAGS的实际依赖

- 来源：[Nixxes How to use DLSS Frame Generation](https://support.nixxes.com/hc/en-us/articles/48432027293971-How-to-use-DLSS-Frame-Generation)。证据等级：A，实际游戏开发商；更新2026-03-03，已读取。
- RTX40+可用普通DLSS FG；启用会同时启用Reflex。支持的游戏可搭DLSS超分或其他超分。
- 明确要求Windows启用Hardware-accelerated GPU scheduling（HAGS），改后重启生效。
- 文内MFG举例仍为2X/3X/4X；不能用该例子否认NVIDIA后来新增的4.5/6X覆盖功能，后者按厂商当前支持判定。
- 未确认：该机HAGS状态。方法：Windows图形默认设置读取；本轮不修改。

## S10 Windows Game Mode、窗口优化和HAGS

- 来源1：[微软Windows11游戏页](https://www.microsoft.com/en-us/windows/windows-11-pc-gaming)。证据等级A，已读取。官方建议核对Game Mode开启，通常默认开启；没有承诺固定FPS提升。
- 来源2：[微软窗口游戏优化](https://support.microsoft.com/en-us/windows/hardware/display-graphics/optimizations-for-windowed-games-in-windows-11)。证据等级A，已读取。对窗口/无边框DX10/11将旧blt模型转flip模型，降低帧延迟，并允许支持设备用VRR/AutoHDR；可以按单游戏关闭，重启游戏生效。
- 来源3：[Microsoft DirectX HAGS原理](https://devblogs.microsoft.com/directx/hardware-accelerated-gpu-scheduling/)。证据等级A，2020原理文章，已读取。把高频调度任务交给GPU硬件调度处理器；官方当年预期多数用户无明显变化，依赖硬件及驱动，不是普遍暴涨帧数开关。
- 判断：现代Windows不能照搬“所有游戏独占全屏永远更低延迟”。按API、呈现模式、捕获需求和实测决定。HAGS既有功能依赖也有驱动差异；有DLSS FG依赖时先保留，不为旧优化清单随手关闭。
- 未确认：OS build、窗口优化和HAGS状态、具体游戏API。方法：winver和设置回读；选择两个代表游戏重复A/B。

## S11 VBS/HVCI：有性能边界，也有明确保护作用

- 来源：[Microsoft Learn：Enable virtualization-based protection of code integrity](https://learn.microsoft.com/en-us/windows/security/hardware-security/enable-virtualization-based-protection-of-code-integrity)。证据等级A，已读取。
- Memory Integrity/HVCI是VBS功能，在隔离环境保护内核代码完整性和内存分配，防止内核被恶意利用。
- 微软说明Intel Kaby Lake+的MBEC、AMD Zen2+的GMET有更好支持；更旧处理器靠模拟，性能影响更大。
- 判断：先找CPU限制证据，再讨论安全与性能取舍；不预先关闭保护，不关闭TPM/SecureBoot来“提速”。游戏反作弊可能另有要求，须单独核对。
- 读取失败记录：微软旧“Options to optimize gaming performance”固定UUID地址本次重定向支持首页，未读到正文，不能写已读到该页的关闭建议。

## S12 PresentMon：必须辨清帧率计数和延迟含义

- 来源：[PresentMon Capture Application README](https://github.com/GameTechDev/PresentMon/blob/main/README-CaptureApplication.md)。证据等级A，工具维护者源码文档；已读取。
- Presented FPS计应用Present调用，Displayed FPS计可测显示帧变化；Frame Type可区分应用渲染与驱动/SDK插值帧。不能在所有抓取路径下盲目把Presented FPS称为“真实游戏逻辑FPS”。
- FrameTime是CPU帧间隔；GPUBusy是GPU实际工作的时长，GPUTime还包含该帧中的等待。
- GPU/Display/Instrumented Latency定义不同；只有可用且正确支持的ClickToPhoton等测量才直接对应那段链路。普通“渲染延迟”不等于完整鼠标到屏幕延迟。
- 判断：关闭FG建原始基线；开启后记录相同捕获工具版本、Frame Type与显示帧时间，必要时高帧率相机/硬件分析器确认。某字段为空不代表0延迟。

## S13 CapFrameX：1% Low不是唯一答案

- 来源：[官方指标解释](https://www.capframex.com/blog/post/Explanation%20of%20different%20performance%20metrics)；[官方功能](https://www.capframex.com/features)；[代码仓库](https://github.com/CXWorld/CapFrameX)。证据等级A，维护者文档；已读取。
- 统计原始对象是帧时间，FPS=1000/毫秒。帧时间P99对应FPS低端分位；percentile与average lows算法不同，跨工具不能直接当同一指标。
- 单个最低帧容易受偶然异常影响；P1也会掩盖极少数但很长的卡顿。完整检查必须包含帧时间图、超阈值卡顿时长及平均帧率。
- 官方支持多轮记录聚合、阈值统计、传感器和对比。不要为了好看删掉真实卡顿异常；加载区间要按事先统一规则排除。
- 判断：同存档同路线，预热后至少3轮，分别报告中位表现和最差轮；高于运行间自然波动的差异才有意义。3轮为本报告建议协议，不是官方规定。

## S14 AMD当前FSR产品页：旧版本硬件结论已变

- 来源：[AMD FSR Technologies](https://www.amd.com/en/products/graphics/technologies/fidelityfx/super-resolution.html)。证据等级A，厂商产品要求；已读取。
- 当前页把FSR4称为FSR Upscaling；ML超分列RX6000、RX7000、RX9000，完整Redstone功能/ML帧生成仍有RX9000+范围。
- 产品页同时区分Spatial/Temporal/ML Upscaling、Native AA、Frame Generation及ML Frame Generation；有FSR某项不证明拥有整套。
- 原生ML超分可直接从游戏菜单开启；部分已有FSR3.1+集成游戏由AMD Software升级，页面对ML FG另有FSR3.1.4+前置条件。
- 判断：报告不能沿用“FSR4只支持RX9000”的旧固定表；具体功能必须由游戏、驱动和GPU三者共同确定。也不能推导出NVIDIA显卡官方支持AMD ML超分。
- 未确认：案例主机显卡是否AMD、驱动版本和游戏支持。方法：先读取硬件清单，再查对应官方功能表。

## S15 Reflex、VRR、VSync和限帧：按目标选择

- 来源：[NVIDIA系统延迟优化指南](https://www.nvidia.com/en-us/geforce/guides/gfecnt/202010/system-latency-optimization-guide/)；[Reflex技术页](https://www.nvidia.com/en-us/geforce/technologies/reflex/)。证据等级A，厂商指南；已读取。前一页属于2020背景资料，对现代窗口呈现的部分需结合S10。
- 有游戏内Reflex时优先使用；它覆盖驱动Ultra Low Latency相同用途。不要指望同时开启两项获得叠加收益。
- 容忍撕裂、追最低延迟时，Reflex+不限制帧率是官方选项。追无撕裂平滑时，G-SYNC+VSync+Reflex可将帧率限制在刷新率下方，避免顶住VSync；其延迟仍略高于不封顶方案。
- 不把“144Hz一律141 FPS”写成所有游戏、所有FG的黄金值。Reflex已有自动限帧行为；外部/驱动帧生成的输入与输出限制也不同。
- 未确认：显示器VRR范围、接口、实际刷新率、限帧发生在FG前还是后。方法：OS/显示器OSD、驱动状态、关闭/开启FG实测曲线。

## 给案例主机的可执行测量协议（工程建议，未实测）

1. 读取硬件：CPU、GPU完整型号和显存、内存容量与通道、系统盘/游戏盘型号和剩余空间、OS build、驱动版本、显示器分辨率/刷新率/VRR，列3–5款常玩游戏和目标。
2. 建三个典型场景：GPU重的室外/光照；CPU重的人群/战斗；资源流送重的高速跑图。不要只用菜单和空场。
3. 原版默认或现有设置留档。关FG采60–120秒，预热后重复3轮；记录帧时间、平均、P1/1% Low算法、卡顿持续时间、GPU Busy、CPU/GPU频率、温度/功耗限制、显存和内存。
4. 一次改一个技术层：游戏画质组合→超分模式→锁基础帧率→原生FG→仅当缺原生FG再试驱动/外部FG。每步保留同路线A/B。
5. 验证动态画面：细栅栏、草叶、电线、头发、字幕/HUD、瞄准镜、粒子、遮挡边缘、快速横移、突然转向。暂停截图不能证明动态稳定。
6. 检查响应：同一输入方式和路线比较开关；鼠标快速瞄准与手柄缓慢镜头分开。缺硬件端到端测量时写“主观响应对比”，不得写精确总延迟结论。
7. 接受标准：目标场景基础帧率稳定，长期卡顿没有恶化，画面和输入代价可接受。显示FPS翻倍但基础帧率跌破目标、UI明显破碎或操作漂浮，则回退。

## 未确认与限制

- 未读取案例主机实时硬件、游戏库或运行日志，无法给该机承诺帧率/提升百分比。
- 未安装、购买、远程执行、改Windows/驱动/BIOS或运行游戏；所有配置项均为报告建议。
- Steam帮助页的性能监控说明本次抓取只回图片，Xbox Game Mode帮助页只回JavaScript提示，未把它们作为已读正文证据；Game Mode改用微软Windows产品页，帧率定义改用PresentMon源码文档。
- 厂商营销图的“X倍”混合画质、超分和插帧条件，不可移植为案例主机预期收益。
- 第三方MOD和非官方硬件解锁不属于本次默认推荐，兼容性、完整性和反作弊要求均未验证。


## S16 追加：RTX2060串流的官方边界

- 来源：[NVIDIA编码解码能力表](https://developer.nvidia.com/video-encode-decode-support-matrix)；证据等级A，已读取2026-11-08。RTX2060/2070列Turing、第7代NVENC、1个NVENC，支持H.264、HEVC含10-bit，不支持AV1编码。具体客户端仍须支持相应硬解；不得把AV1设为2060主机方案。
- 来源：[Sunshine官方配置](https://docs.lizardbyte.dev/projects/sunshine/latest/md_docs_2configuration.html)；证据等级A，已读取2026-11-08。NVENC默认P1，P1→P7越高压缩质量越高但编码延迟越大；官方建议只在网络/解码限制时改，网络充足可通过码率改善画质。`nvenc_latency_over_power`默认开启，官方不推荐关闭，否则编码延迟会明显上升。
- 来源：[Sunshine官方故障排查](https://github.com/LizardByte/Sunshine/blob/master/docs/troubleshooting.md)；证据等级A，已读取2026-11-08。实时串流重在低抖动、低丢包与一致性；主机到客户端存在慢段时，60fps的16ms突发包会在中间设备堆积，码率过高会溢出丢包。
- 判断：对2060主机，先建1080P60、NVENC H.264/HEVC的稳定基线，再试1440P；分开记录游戏渲染、主机捕获编码、网络、客户端解码/呈现。不能用吞吐高或ping低单独证明串流顺滑。
- 版本限制：用户使用Sunshine Foundation分支，其选项名称、默认和捕获路径须读实际配置与日志，以上上游资料不能证明该分支逐项完全相同。未核查此分支代码，未修改串流配置。


## S17 追加：9600KF与B365M D2V硬件扩展边界

- [Intel i5-9600KF官方规格](https://www.intel.com/content/www/us/en/products/sku/190884/intel-core-i59600kf-processor-9m-cache-up-to-4-60-ghz/specifications.html)：6核6线程，单核最高4.6GHz，DDR4-2666、双通道，PCIe3.0；最高睿频不是保证全核游戏中恒定4.6GHz。证据等级A，已读取2026-11-08。
- [GIGABYTE B365M D2V rev1.0规格](https://www.gigabyte.com/Motherboard/B365M-D2V-rev-10/sp)：2个内存槽、最大32GB，DDR4-2666/2400/2133；2666/XMP需要8/9代i5/i7/i9。一个PCIe3.0 x16槽、两个x1槽；一个M.2（SATA/PCIe3.0x4/x2）。证据等级A，已读取2026-11-08。
- 判断：若实机确为该revision且2×8GB已占满，升32GB应换2×16GB，不能建议再加2×8GB；不默认推荐DDR4-3600套条或把XMP等同突破主板频率范围。若CPU/板/内存支持，2400→2666的收益属于待实测，容量不足和GPU显存不足也不能靠小幅内存频率解决。
- 未确认：实机revision、BIOS、内存SPD、温度和功率限制。读主板标识和SPD再决定，不做BIOS升级或超频。

- [Intel i5核显官方对照PDF](https://cdrdv2-public.intel.com/841760/Intel-Core-i5-HD-GFX.pdf)的i5-9600KF行标Processor Graphics为No*；因此该CPU没有集成图形，不能规划Intel核显QuickSync作为现有主机的无成本编码替代。已读取官方PDF。
