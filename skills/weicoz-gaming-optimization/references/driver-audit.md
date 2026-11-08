# NVIDIA驱动只读核查与逐游戏建议

## 证据层次

| 层 | 能证明 | 不能证明 |
|---|---|---|
| Steam manifest/目录 | 发现条目、文件存在 | 已激活、完整安装、最近游玩、能够运行 |
| NVIDIA App扫描缓存 | 当时识别结果和兼容字段 | 当前UI可用、运行时生效 |
| NVAPI DRS | 保存值、继承位置、预定义/用户值、Profile关联 | 游戏最终执行某模型 |
| DLL版本/哈希 | 磁盘组件身份 | 正在加载、已选K/M/L、驱动未覆盖 |
| 进程模块 | 当前加载路径 | 具体模型与输出帧被串流捕获 |
| DLSS Overlay | 对应版本可观测的运行态信息 | 无观测项的真实模型、完整客户端体验 |
| 串流端采样 | 客户端收到的画面和统计 | 未测的端到端绝对输入延迟 |

## 盘点范围

1. 读取硬件、驱动与App产品版本；CEF文件版本不可当App版本。显示器EDID、主机桌面刷新率和客户端屏幕分别记录。
2. 读取已配置的游戏库、App游戏条目和明确游戏目录；必要时扩展到用户授权的库外位置，不扫无关私人文件。记录完整度边界。
3. 合并符号链接、重复目录和同一游戏不同启动入口，保留路径证据；空目录/备份不计作可玩游戏。软件和公共运行库另列。
4. 枚举nvngx组件，分别列SR、RR、FG及备份。多路径版本不同要验证加载，不随意删旧文件或恢复备份。
5. 查当前全局Profile及相关游戏Profile；不仅查Base Profile，因为当前全局配置未必是它。按实际EXE/路径匹配，自定义改名程序尤其重要。
6. 只读取设置。不得调用设置保存、创建/删除Profile或加载外部配置来冒充只读。保留原始错误状态，不把失败后的默认数值当数据。

## NVAPI读取要点

官方定义：[nvapi.h](https://github.com/NVIDIA/nvapi/blob/main/nvapi.h)、[NvApiDriverSettings.h](https://github.com/NVIDIA/nvapi/blob/main/NvApiDriverSettings.h)、[nvapi_interface.h](https://github.com/NVIDIA/nvapi/blob/main/nvapi_interface.h)。使用前核对当前头文件；以下是历史快照。

允许的流程：Initialize → DRS_CreateSession → DRS_LoadSettings → GetCurrentGlobalProfile/EnumProfiles/GetProfileInfo/EnumApplications/GetSetting → DestroySession。LoadSettings读取驱动数据库到会话；不调用SaveSettings/SetSetting/Import/CreateProfile/DeleteProfile。

GetSetting成功时保存settingId、settingType、settingLocation、isCurrentPredefined、isPredefinedValid和对应类型的currentValue。返回SETTING_NOT_FOUND时写“未发现键”，不得写“0/关闭”。其他错误保留状态并解释未确认；不是全部当作缺失。

| 历史设置ID | 含义 | 当时枚举 |
|---|---|---|
| 0x10E41E01 | DLSS SR覆盖开关 | 0关闭、1开启 |
| 0x10E41DF3 | DLSS SR模型预设 | K=11、L=12、M=13；0是无指定预设 |
| 0x10AFB768 | SR模式覆盖 | 性能0、平衡1、质量2、应用控制3、DLAA4、超级性能5、自定义6 |
| 0x10E41DF5 | SR缩放比例覆盖 | 依据官方类型/定义解析，不能凭数字猜 |
| 0x1057EB71 | 电源状态 | 1最高性能优先 |
| 0x10835002 | 驱动限帧 | 0禁用；非零按官方FPS定义解读 |
| 0x00CE2691 | 纹理过滤质量 | 0质量 |

预渲染帧设置不存在不能推断Low Latency Mode关闭；未查询DSR/G-SYNC就列未验证。只根据官方定义解码公开键，内部stateMask不猜位含义。默认值、继承值和用户显式值分别报告。

历史本地探针使用Windows PowerShell内存编译C#并调nvapi64.dll。ABI结构的大小、版本、打包和字符串长度须逐项核对官方头文件；P/Invoke失败停止，不循环试错写驱动。远程调用复用已授权SSH入口，不硬编码主机、地址、用户名或端口；不得将敏感输出回显。

## App字段与组件冲突

- Disable_SR_Model_Override：模型覆盖限制。
- Disable_SR_Override：模式覆盖限制。
- 两者不同；允许K/L/M并不自动允许在App里改质量/平衡。
- 有DLL但模型覆盖禁用：当前原生实现仍可能用DLSS，不能说“游戏不支持DLSS”。
- 缓存允许但没有组件：检查安装版本/路径/运行时，不凭一项推断。
- NIS缓存enabled或sharpen只证明记录；不认识的factor不自动转成百分比。是否正在缩放/锐化另验。

## 推荐规则

先给当前配置，再给建议，最后给验证方式。对RTX20/30候选顺序为当前实现→K对比→M单独实验；L的低输入高输出组合另立实验，不默认全局应用。不同GPU重核开销，不能把2060方案照搬到新卡。

缺官方覆盖入口就写条件性试验，不直接通过改DLL/注册表强行解锁。模式仅为候选，第一轮只改模型。没有DLL或原生DLSS证据的游戏保留应用控制，不宣称绝对不可能支持。

逐游戏行至少写：名称/实际EXE、证据日期、已保存覆盖、组件、App兼容状态、推荐模型、模式起点、驱动其他项、需验证项。相同电源/NIS/过滤设置引用公共模板，保留每款特殊边界。
