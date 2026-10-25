<!--
作者 / Author: XCrane
项目 / Project: CRA NAO Toolbox
说明 / Description: NAO 机器人验修、源码运行与发布说明
-->

<div align="center">

<a href="https://github.com/CCU-Robotics-Association">
  <img src="https://raw.githubusercontent.com/CCU-Robotics-Association/.github/main/profile/assets/logo.svg" width="132" alt="CCU Robotics Association Logo">
</a>

# CCU Robotics Association

### NAO 机器人验修工具箱 · CRA NAO Toolbox

CCU 机器人协会 · 2026 —— Future

[![Organization](https://img.shields.io/badge/CCU-Robotics_Association-4C1D95?style=flat-square&labelColor=181717&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4KPHN2ZyB3aWR0aD0iNTAxIiBoZWlnaHQ9IjQ3MCIgdmlld0JveD0iMCAwIDUwMSA0NzAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI%2BCiAgPHBhdGggZD0iTSA4OSA5NSBMIDAgNDY5IEwgNDQyIDQ2OSBMIDQ1MCA0MTQgTCAzMTkgMjMwIEwgMjQxIDIzMCBMIDM2OCA0MTEgTCA3MyA0MTAgTCAxNDkgOTcgWiBNIDExMSAxIEwgOTkgNTMgTCA0NDQgNTMgTCA0NDQgNjYgTCA0MjggMTYxIEwgNDc3IDIyNSBMIDUwMCAwIFoiIGZpbGw9IndoaXRlIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiLz4KPC9zdmc%2BCg%3D%3D)](https://github.com/CCU-Robotics-Association)
![Python 2.7](./assets/python-badge.svg)
![NAOqi](https://img.shields.io/badge/NAOqi_2.8-ffffff?style=flat-square)

[**官网(Website) »**](https://ccu-robotics-association.github.io/) | [**GitHub 主页 »**](https://github.com/CCU-Robotics-Association) | [**下载工具(Download) »**](https://github.com/CCU-Robotics-Association/CRA-NAO/releases/tag/v1.1.1)

> **一  同  奋  进  前  行  ，  共  就  非  凡  之  事**

</div>

---

***CRA NAO Toolbox*** 为批量返修的 NAO 机器人提供统一验修流程，支持图形界面、命令行检查、批量清单与离线报告

> [!NOTE]
> 普通使用者下载对应系统的完整安装包即可，无需另装 Python 或 NAOqi SDK；源码运行和重新打包的环境要求见后文

## <img src="./assets/icons/compass.svg" width="22" height="22" alt=""> Navigation | 导航

<table>
<tr>
<td width="50%" valign="top">

<img src="./assets/icons/bot.svg" width="28" height="28" alt="">

### Inspection | 使用与验修

- [工具下载](#downloads)
- [快速开始](#quick-start)
- [验收模式](#profiles)
- [检测范围](#coverage)
- [报告与日志](#reports)
- [运动验收](#motion)

</td>
<td width="50%" valign="top">

<img src="./assets/icons/code-xml.svg" width="28" height="28" alt="">

### Development | 源码与维护

- [源码运行](#source)
- [批量清单与配置](#configuration)
- [打包发布](#build)
- [项目结构](#structure)
- [常见问题](#faq)
- [复测与反馈](#feedback)

</td>
</tr>
</table>

<a name="downloads"></a>

## <img src="./assets/icons/download.svg" width="22" height="22" alt=""> Downloads | 工具下载

当前发布版本为 **1.1.1**，完整附件与更新说明见 [v1.1.1 Release](https://github.com/CCU-Robotics-Association/CRA-NAO/releases/tag/v1.1.1)

| 平台 | 安装包 | 启动方式 |
| :--- | :--- | :--- |
| Windows x64 | [NAO_Toolbox-1.1.1-win64.zip](https://github.com/CCU-Robotics-Association/CRA-NAO/releases/download/v1.1.1/NAO_Toolbox-1.1.1-win64.zip) | 完整解压后运行 `NAO_Toolbox.exe` |
| Linux x86_64 | [NAO_Toolbox-1.1.1-linux-x86_64.tar.gz](https://github.com/CCU-Robotics-Association/CRA-NAO/releases/download/v1.1.1/NAO_Toolbox-1.1.1-linux-x86_64.tar.gz) | 在图形桌面中运行 `./NAO_Toolbox` |
| macOS Intel x86_64 | [NAO_Toolbox-1.1.1-macos-x86_64.tar.gz](https://github.com/CCU-Robotics-Association/CRA-NAO/releases/download/v1.1.1/NAO_Toolbox-1.1.1-macos-x86_64.tar.gz) | 解压后打开 `NAO_Toolbox.app` |

下载后可使用同一 Release 中的 [SHA256 校验清单](https://github.com/CCU-Robotics-Association/CRA-NAO/releases/download/v1.1.1/SHA256SUMS-1.1.1.txt) 核对安装包

> [!IMPORTANT]
> macOS 包面向 Intel x86_64，使用 ad-hoc 签名，未经过 Apple 公证；Apple Silicon 原生运行及 Rosetta 运行未经验证

<a name="quick-start"></a>

## <img src="./assets/icons/wrench.svg" width="22" height="22" alt=""> Quick Start | 快速开始

### Requirements | 运行条件

| 项目 | 要求 |
| :--- | :--- |
| 电脑 | Windows 10 / 11 x64，或对应安装包支持的 Linux、macOS x86_64 环境 |
| NAO | 面向 NAOqi 2.8 环境，当前构建配置使用 pynaoqi 2.8.6 SDK |
| 网络 | 电脑与机器人网络互通，NAOqi 默认端口为 `9559` |
| 依赖 | 安装包包含 Python、Tk 与 NAOqi 通信库，Linux 仍需图形桌面和所需系统库 |

### Procedure | 开始一次验收

1. 完整解压安装包，启动对应平台的程序，首次加载内置组件时请稍候
2. 填写机器人编号，例如 `01`、`02`、`03`，以及当前 IP 地址
3. 核对报告保存目录，点击“测试连接”，确认电脑能够访问机器人
4. 选择 `Guided`，点击“开始检查”，按语音和弹窗完成现场操作
5. 检查结束后点击“打开最近报告”，双击结果表中的项目查看详细指标

<a name="profiles"></a>

## <img src="./assets/icons/scan-eye.svg" width="22" height="22" alt=""> Profiles | 验收模式

界面模式使用英文名称，命令行参数使用对应的小写值

| 界面 | 命令行 | 内容 | 使用场景 |
| :---: | :---: | :--- | :--- |
| `Quick` | `quick` | 自动检查系统、诊断、传感器、相机与音频通路 | 批量初筛 |
| `Guided` | `guided` | Quick + 触摸、胸键、脚部开关、灯光及声像人工确认 | 录像验修 |
| `Full` | `full` | Guided + 可选关节运动、行走及检查后快照 | 完整验修 |

> [!NOTE]
> 选择 `Full` 不会自动授权主动运动，关节运动和行走仍需分别授权并满足前置条件

<a name="coverage"></a>

## <img src="./assets/icons/cpu.svg" width="22" height="22" alt=""> Coverage | 检测范围

| 类别 | 检查内容 | 记录内容 |
| :--- | :--- | :--- |
| 连接与系统 | 网络、RPC 延迟、型号、版本、服务及 Autonomous Life 状态 | 系统信息、连接数据 |
| 内置诊断 | ALDiagnosis、诊断键、系统通知、板卡 Ack/Nack 增量 | 诊断快照、板卡计数 |
| 电池与温度 | 电量、电流、供电状态、关节温度与温度状态 | 检查前后快照 |
| 关节与姿态 | 命令角、传感角、刚度、IMU、足底 FSR | 关节与惯导采样、压力数据 |
| 声纳 | 左右距离及有效性，交互时使用约 0.40 m 平面标靶 | 距离采样与统计 |
| 相机与音频 | 上下相机帧、亮度、对比度、时间戳；麦克风能量与扬声器听音 | BMP 图像、帧指标、音频能量 |
| 触摸与按键 | 头部、左手、右手各任选一处；胸键及四个脚部开关 | 按下与释放的响应周期 |
| LED | 眼、耳、胸、脚灯的颜色、亮度与坏点人工确认 | 指令结果、人工结论 |
| 主动运动 | 小幅关节跟踪与回位、低速短距离行走 | 目标与实测、误差、电流、温度、稳定性数据 |
| 日志 | 工具执行日志、可选 SSH 系统日志与离线关键词分析 | 原始日志、故障线索 |

<a name="reports"></a>

## <img src="./assets/icons/file-text.svg" width="22" height="22" alt=""> Reports | 报告与日志

### Location | 保存位置

| 启动方式 | 默认报告根目录 |
| :--- | :--- |
| Windows 安装包 | `%USERPROFILE%/Documents/NAO_Reports/` |
| Linux / macOS 安装包 | `~/Documents/NAO_Reports/` |
| 源码 GUI | 项目目录下的 `reports/` |
| 命令行 | 当前工作目录下的 `reports/`，Windows 用 `-Output`、Linux / macOS 用 `--output` 指定 |

GUI 可直接修改报告目录，每次运行按“机器人编号 / 时间与 IP”建立独立文件夹

```text
<报告根目录>/<机器人编号>/<时间与 IP>/
├── report.html        汇总报告，可离线打开
├── report.json        完整结果、阈值与原始指标
├── tests.csv          逐项结果
├── metrics.csv        展平后的测量数据
├── run.log            工具执行日志
├── artifacts/         相机图像、诊断快照和采样数据
└── robot_logs/        可选的 SSH 系统日志
```

### Results | 结果含义

| 状态 | 含义 | 处理方式 |
| :---: | :--- | :--- |
| `PASS` | 该项目的自动条件及所需人工确认均通过 | 留档 |
| `WARN` | 边界值、能力限制或仍需专项确认 | 查看数据并复核 |
| `FAIL` | 诊断故障、异常数据或人工确认不通过 | 记录问题并复修 |
| `SKIP` | 未授权、能力不可用或安全条件不满足 | 查看跳过原因 |
| `ERROR` | 程序或 NAOqi 调用异常 | 查看日志与异常详情 |

汇总结论为 `ACCEPT`、`ACCEPT_WITH_NOTES` 或 `REJECT`

> [!IMPORTANT]
> 结论只针对本次所选项目，有 `WARN` 或 `SKIP` 时仍需复核，未选择或未执行的项目不代表通过

### System Logs | 系统日志

`run.log`、诊断与传感器数据随验收保存，需要机器人原生系统日志时，在界面勾选“采集系统日志”并配置 SSH 用户、端口和私钥

电脑需有可用的 `ssh` 命令，机器人需已授权密钥登录

<details>
<summary><strong>命令行采集与离线分析</strong></summary>

Windows 命令行采集：

```bat
run.bat -Ip 192.168.1.101 -RobotId 01 -Profile guided -CollectLogs -SshKey C:/Keys/nao_ed25519
```

已有日志可离线分析：

```bat
python analyze_nao_logs.py C:/NAO_Logs --output log-analysis.json
```

关键词命中是排查线索，应结合诊断、原始数据和人工观察判断

</details>

<a name="motion"></a>

## <img src="./assets/icons/shield-check.svg" width="22" height="22" alt=""> Motion | 运动验收

默认关闭主动运动

| 项目 | 现场确认 | 程序前置条件 |
| :--- | :--- | :--- |
| 关节小幅运动 | 勾选授权，输入 `MOVE` | 电池、温度、静态关节通过，运动相关诊断与保护检查满足要求 |
| 短距离行走 | 同时授权关节与行走，输入 `WALK-<编号>` | 同一流程中的关节运动、IMU 通过，FSR 与稳定性检查满足要求 |

> [!WARNING]
> 主动运动需具备相应场地与现场看护条件，界面的“停止后续项目”用于等待当前项目安全结束，不能作为急停按钮

<a name="source"></a>

## <img src="./assets/icons/code-xml.svg" width="22" height="22" alt=""> Source | 源码运行

源码运行需要 **64 位 Python 2.7**、Tkinter，以及与操作系统、机器人 NAOqi 版本匹配的厂家 pynaoqi SDK

[requirements.txt](./requirements.txt) 没有 PyPI 运行依赖，pynaoqi 由厂家 SDK 提供

### Windows | Windows 启动

在本目录打开终端：

```bat
conda env create -f environment.yml
conda activate NAO
run_gui.bat
```

启动器会查找 `NAO` 环境和本地 SDK，也可指定路径：

```bat
run_gui.bat -PythonExe C:/path/to/python.exe -SdkRoot C:/path/to/pynaoqi
```

### Linux / macOS | Unix 启动

准备对应平台的 Python 2.7 x64、Tkinter 与 SDK，再指定实际路径：

```bash
export PYTHON_EXE="/path/to/python2.7"
export PYNAOQI_SDK="/path/to/pynaoqi"
sh run_gui.sh
```

命令行示例：

```bash
sh run.sh --ip 192.168.1.101 --robot-id 01 --profile guided
```

> [!NOTE]
> Linux / macOS 启动器使用 `--profile` 等 Python 参数，Windows `run.bat` 使用 `-Profile` 等 PowerShell 参数，两者不要混用

### Commands | Windows 常用命令

<details>
<summary><strong>检查项目、单台验收与语音设置</strong></summary>

```bat
:: 列出全部验收项目
run.bat -ListTests

:: 单台录像验收
run.bat -Ip 192.168.1.101 -RobotId 01 -Profile guided

:: 自动快检，关闭验收播报
run.bat -Ip 192.168.1.101 -RobotId 01 -Profile quick -NoVoice

:: 同时跳过测试音
run.bat -Ip 192.168.1.101 -RobotId 01 -Profile quick -NoVoice -Skip audio
```

</details>

<details>
<summary><strong>主动运动检查</strong></summary>

```bat
:: 关节检查，仍需完成现场确认
run.bat -Ip 192.168.1.101 -RobotId 01 -Profile full -AllowMotion

:: 关节与地面行走检查，须具备相应场地和看护条件
run.bat -Ip 192.168.1.101 -RobotId 01 -Profile full -AllowMotion -AllowWalk
```

</details>

<a name="configuration"></a>

## <img src="./assets/icons/wrench.svg" width="22" height="22" alt=""> Configuration | 批量清单与配置

### Inventory | 批量清单

复制 [robots.example.csv](./robots.example.csv)，填写编号和 IP：

```bat
copy robots.example.csv robots.csv
run.bat -Inventory robots.csv -Profile quick
```

```csv
robot_id,ip,port,notes,enabled
01,192.168.1.101,9559,第一批,1
02,192.168.1.102,9559,第一批,1
```

使用 `-Profile guided` 可逐台引导验收，任一运动项目失败或异常时，程序会停止批次，先人工处置该机器人再重新启动

### Thresholds | 阈值配置

基于 [config.example.json](./config.example.json) 创建本地配置：

```bat
copy config.example.json config.local.json
run.bat -Ip 192.168.1.101 -RobotId 01 -Profile guided -Config config.local.json
```

<a name="build"></a>

## <img src="./assets/icons/cpu.svg" width="22" height="22" alt=""> Build | 打包发布

本目录提供 [Windows 构建脚本](./build_exe.ps1) 与 [Linux / macOS 构建脚本](./scripts/build_unix.py)，各平台在对应的 x86_64 环境中构建

> [!IMPORTANT]
> 当前仓库源码未包含构建脚本引用的 `docs/`，也缺少 `packaging/` 下供 Windows 发布包使用的说明文本。重新构建前需补齐这些资源，否则构建或归档会失败；普通使用者可使用上方已发布的安装包

### Dependencies | 构建依赖

在已经配置好 SDK 的 Python 2.7 x64 构建环境中，按顺序安装锁定依赖，PyInstaller 固定为 3.6：

```bat
python -m pip install --require-hashes --no-deps -r packaging/requirements-bootstrap.lock
python -m pip install --require-hashes --no-deps --no-build-isolation --no-use-pep517 -r requirements-build.txt
```

补齐构建资源后，Windows 执行：

```bat
build_exe.bat
```

需要指定环境与 SDK 时：

```bat
build_exe.bat -PythonExe C:/path/to/python.exe -SdkRoot C:/path/to/pynaoqi
```

Linux / macOS 设置前述 `PYTHON_EXE` 与 `PYNAOQI_SDK` 后执行：

```bash
sh build_unix.sh
```

### Artifacts | 构建产物

版本号由 [nao_diag/__init__.py](./nao_diag/__init__.py) 决定，当前为 `1.1.1`

| 平台 | 程序 | 安装包 |
| :--- | :--- | :--- |
| Windows | `dist/NAO_Toolbox.exe` | `release/NAO_Toolbox-1.1.1-win64.zip` |
| Linux | `dist/NAO_Toolbox` | `release/NAO_Toolbox-1.1.1-linux-x86_64.tar.gz` |
| macOS | `dist/NAO_Toolbox.app` | `release/NAO_Toolbox-1.1.1-macos-x86_64.tar.gz` |

构建脚本会检查内置 Python、NAOqi SDK 与 Tk，生成安装包及构建记录；运行环境检查不连接机器人，不能代替实机验收

发布时使用完整安装包，并保留对应 `.sha256`、`.build.json` 或校验清单；`build/`、`dist/` 和 `release/` 不进入源码版本管理

重新分发时需核对厂家 SDK 及第三方组件的许可要求

<a name="structure"></a>

## <img src="./assets/icons/folder-open.svg" width="22" height="22" alt=""> Structure | 项目结构

<details>
<summary><strong>展开源码与启动文件</strong></summary>

```text
NAO_inspection_repair/
├── nao_gui.py                 GUI 入口与打包运行环境
├── nao_diagnostic.py          命令行入口
├── analyze_nao_logs.py        离线日志分析入口
├── nao_diag/
│   ├── gui.py                桌面界面
│   ├── desktop.py            跨平台桌面适配
│   ├── cli.py                命令行与批量清单
│   ├── runner.py             验收流程调度
│   ├── client.py             NAOqi 通信
│   ├── context.py            日志、证据与人工确认
│   ├── config.py             配置与阈值校验
│   ├── model.py              结果模型
│   ├── report.py             报告输出
│   ├── voice.py              语音播报
│   ├── remote_logs.py        SSH 日志采集
│   ├── log_analysis.py       日志分析
│   ├── compat.py             Python 2/3 兼容处理
│   └── checks/               自动、引导与运动检查
├── scripts/                   环境查找、原生构建与构建记录
├── packaging/                 Unix 使用说明与构建输入锁定
├── run_gui.bat                Windows GUI 启动
├── run.bat                    Windows 命令行启动
├── run_gui.sh                 Linux / macOS GUI 启动
├── run_gui.command            macOS Finder 启动入口
├── run.sh                     Linux / macOS 命令行启动
├── build_exe.bat              Windows 打包入口
├── build_unix.sh              Linux / macOS 打包入口
├── nao_toolbox.spec           PyInstaller 配置
├── environment.yml           Conda 环境配置
├── config.example.json        阈值配置示例
└── robots.example.csv         批量机器人清单示例
```

</details>

<a name="faq"></a>

## <img src="./assets/icons/circle-dot.svg" width="22" height="22" alt=""> FAQ | 常见问题

<details>
<summary><strong>安装包启动较慢，是否需要另装 Python</strong></summary>

完整安装包已包含运行组件，无需另装 Python 或 Conda，首次解包和加载 SDK 可能需要等待

启动异常时可查看 `gui_error.log`，Windows 位于 `%LOCALAPPDATA%/NAO_Toolbox/`，macOS 位于 `~/Library/Logs/NAO_Toolbox/`，Linux 位于 `${XDG_STATE_HOME:-~/.local/state}/NAO_Toolbox/`

</details>

<details>
<summary><strong>源码提示找不到 Python 或 pynaoqi</strong></summary>

确认使用 64 位 Python 2.7，并为当前操作系统准备匹配的厂家 SDK。Windows 可通过 `-PythonExe` 和 `-SdkRoot` 指定，Linux / macOS 使用 `PYTHON_EXE` 和 `PYNAOQI_SDK`

</details>

<details>
<summary><strong>选择 Full 后为什么没有执行关节或行走</strong></summary>

查看项目的 `SKIP` 原因，核对是否开启对应授权、完成口令确认，以及电池、温度、诊断和前置检查是否满足要求

</details>

<a name="feedback"></a>

## <img src="./assets/icons/book-open.svg" width="22" height="22" alt=""> Feedback | 复测与反馈

本项目用于协会设备维护、功能验收与机器人项目开发，复测时请保留：

- 机器人编号、型号与 NAOqi 版本
- 使用的工具版本、验收模式与阈值配置
- 对应项目的错误摘要、报告和日志

需要重装系统时，参见 [NAO 机器人刷机教程](../Flasher/README.md)

---

<div align="center">

### CCU · ROBOTICS · ASSOCIATION

<sub>NAO 机器人验修工具箱 | CRA NAO</sub>

[**官网(Website)**](https://ccu-robotics-association.github.io/) · [**GitHub 主页**](https://github.com/CCU-Robotics-Association) · [**工具发布(Releases)**](https://github.com/CCU-Robotics-Association/CRA-NAO/releases/tag/v1.1.1)

<sub>CCU Robotics Association</sub>

</div>
