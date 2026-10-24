<!--
@ Project            : NAO 机器人验修工具箱
@ Description        : 项目介绍、验收操作、源码运行与发布说明
@ Author             : XCrane
-->

<div align="center">

# CRA NAO Toolbox

### CCU 机器人协会 · NAO 机器人验修工具箱

**CCU Robotics Association · NAO Inspection & Repair Acceptance**

![Windows](https://img.shields.io/badge/Windows-x64-0078D4?style=flat-square)
![Python](https://img.shields.io/badge/Python-2.7-3776AB?style=flat-square&logo=python&logoColor=white)
![NAOqi](https://img.shields.io/badge/NAOqi-2.8-orange?style=flat-square)

Edited：**XCrane**

</div>

---

<div align="center">

[项目简介](#overview) · [EXE 使用](#quick-start) · [验收模式](#profiles) ·
[检测范围](#coverage) · [报告与日志](#reports) ·
[源码运行](#source) · [打包发布](#build)

</div>

<a id="overview"></a>

## 项目简介

`CRA NAO Toolbox` 为批量返修的 NAO 机器人提供统一验修流程。

<a id="quick-start"></a>

## EXE 使用

### 运行条件

| 项目 | 要求 |
| --- | --- |
| 电脑 | 64 位 Windows 10 / 11 |
| 机器人 | 当前 EXE 内置 pynaoqi 2.8.6 SDK，面向 NAOqi 2.8 环境 |
| 网络 | 电脑与机器人网络互通，NAOqi 默认端口为 `9559` |
| 软件依赖 | EXE 已包含 Python、Tk 和 NAOqi 通信库，无需另装 Python 或 Conda |

发布包文件名为 `NAO_Toolbox-1.0.0-win64.zip`。自行构建的文件位于项目的 `release/` 目录；构建方式见[打包发布](#build)。

### 开始一次验收

1. 完整解压发布包，双击 `NAO_Toolbox.exe`。首次加载内置组件时请稍候。
2. 填写机器人编号，例如 `01`、`02`、`03`，以及当前 IP 地址。
3. 点击“测试连接”，确认电脑能够访问机器人。
4. 选择 `Guided`，点击“开始检查”，按语音和弹窗完成现场操作。
5. 检查结束后点击“打开最近报告”。双击结果表中的项目可查看详细指标。

发布包包含：

```text
NAO_Toolbox-1.0.0-win64/
├── NAO_Toolbox.exe
├── config.example.json
└── docs/
    ├── OPERATOR_CHECKLIST.md
    └── THRESHOLDS.md
```

<a id="profiles"></a>

## 验收模式

界面模式使用英文名称，命令行参数使用对应的小写值。

| 界面 | 命令行 | 内容 | 使用场景 |
| --- | --- | --- | --- |
| `Quick` | `quick` | 自动检查系统、诊断、传感器、相机与音频通路 | 批量初筛 |
| `Guided` | `guided` | Quick + 触摸、胸键、脚部开关、灯光及声像人工确认 | 录像验修|
| `Full` | `full` | Guided + 可选关节运动、行走及检查后快照 | 完整验修 |

<a id="coverage"></a>

## 检测范围

| 类别 | 检查内容 | 记录内容 |
| --- | --- | --- |
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

<a id="reports"></a>

## 报告与日志

### 保存位置

| 启动方式 | 默认报告根目录 |
| --- | --- |
| EXE | `%USERPROFILE%/Documents/NAO_Reports/` |
| 源码 GUI | 项目目录下的 `reports/` |
| 命令行 | 当前工作目录下的 `reports/`，可用 `-Output` 指定 |

GUI 可直接修改报告目录。每次运行按“机器人编号 / 时间与 IP”建立独立文件夹：

```text
<报告根目录>/<机器人编号>/<时间与 IP>/
├── report.html        汇总报告，可离线打开
├── report.json        完整结果、阈值与原始指标
├── tests.csv          逐项结果
├── metrics.csv        展平后的测量数据
├── run.log            本工具的执行日志
├── artifacts/         相机图像、诊断快照和采样数据
└── robot_logs/        可选的 SSH 系统日志
```

### 结果含义

| 状态 | 含义 | 处理方式 |
| --- | --- | --- |
| `PASS` | 该项目的自动条件及所需人工确认均通过 | 留档 |
| `WARN` | 边界值、能力限制或仍需专项确认 | 查看数据并复核 |
| `FAIL` | 诊断故障、异常数据或人工确认不通过 | 记录问题并复修 |
| `SKIP` | 未授权、能力不可用或安全条件不满足 | 查看跳过原因 |
| `ERROR` | 程序或 NAOqi 调用异常 | 查看日志与异常详情 |

汇总结论为 `ACCEPT`、`ACCEPT_WITH_NOTES` 或 `REJECT`。结论针对本次所选项目；有 `WARN/SKIP` 时需复核，未选择的项目不代表通过。

### 系统日志

`run.log`、诊断与传感器数据随验收保存。需要机器人原生系统日志时，在界面勾选“采集系统日志”并配置 SSH 用户、端口和私钥；电脑还需有可用的 `ssh` 命令，机器人需已授权密钥登录。

命令行采集：

```bat
run.bat -Ip 192.168.1.101 -RobotId 01 -Profile guided -CollectLogs -SshKey C:/Keys/nao_ed25519
```

已有日志可离线分析：

```bat
python analyze_nao_logs.py C:/NAO_Logs --output log-analysis.json
```

关键词命中是排查线索，应结合诊断、原始数据和人工观察判断。

<a id="motion"></a>

## 运动验收

默认关闭主动运动。

| 项目 | 现场确认 | 程序前置条件 |
| --- | --- | --- |
| 关节小幅运动 | 勾选授权，输入 `MOVE` | 电池、温度、静态关节通过，运动相关诊断与保护检查满足要求 |
| 短距离行走 | 同时授权关节与行走，输入 `WALK-<编号>` | 同一流程中的关节运动、IMU 通过，FSR 与稳定性检查满足要求 |

<a id="source"></a>

## 源码运行

### 环境准备

EXE 使用者可跳过本节。源码运行需要 **64 位 Python 2.7**、Tkinter 以及与机器人 NAOqi 版本匹配的厂家 pynaoqi SDK。

```bat
conda env create -f environment.yml
conda activate NAO
run_gui.bat
```

启动器会查找 `NAO` 环境和本地 SDK，也可指定路径：

```bat
run_gui.bat -PythonExe C:/path/to/python.exe -SdkRoot C:/path/to/pynaoqi
```

`requirements.txt` 中没有 PyPI 运行依赖，pynaoqi 由厂家 SDK 提供。当前打包版固定使用 2.8 SDK；其他 NAOqi 版本需使用匹配 SDK 运行源码或重新构建。

### 常用命令

```bat
:: 列出全部验收项目
run.bat -ListTests

:: 单台录像验收
run.bat -Ip 192.168.1.101 -RobotId 01 -Profile guided

:: 自动快检，关闭验收播报
run.bat -Ip 192.168.1.101 -RobotId 01 -Profile quick -NoVoice

:: 同时跳过测试音
run.bat -Ip 192.168.1.101 -RobotId 01 -Profile quick -NoVoice -Skip audio

:: 关节检查
run.bat -Ip 192.168.1.101 -RobotId 01 -Profile full -AllowMotion

:: 关节与地面行走检查，须具备相应场地和看护条件
run.bat -Ip 192.168.1.101 -RobotId 01 -Profile full -AllowMotion -AllowWalk
```

### 批量清单与配置

复制[清单示例](robots.example.csv)，填写编号和 IP：

```bat
copy robots.example.csv robots.csv
run.bat -Inventory robots.csv -Profile quick
```

```csv
robot_id,ip,port,notes,enabled
01,192.168.1.101,9559,第一批,1
02,192.168.1.102,9559,第一批,1
```

使用 `-Profile guided` 可逐台引导验收。任一运动项目失败或异常时，程序会停止批次，先人工处置该机器人再重新启动。

自定义阈值使用[配置示例](config.example.json)：

```bat
copy config.example.json config.local.json
run.bat -Ip 192.168.1.101 -RobotId 01 -Profile guided -Config config.local.json
```

<a id="build"></a>

## 打包发布

在配置好 SDK 的 Python 2.7 x64 环境中执行：

```bat
conda activate NAO
python -m pip install -r requirements-build.txt
build_exe.bat
```

指定环境或 SDK：

```bat
build_exe.bat -PythonExe C:/path/to/python.exe -SdkRoot C:/path/to/pynaoqi
```

| 产物 | 路径 |
| --- | --- |
| 单文件程序 | `dist/NAO_Toolbox.exe` |
| 完整发布包 | `release/NAO_Toolbox-1.0.0-win64.zip` |
| 内置组件检查记录 | `build/runtime-check-*.json` |

构建脚本使用 PyInstaller 3.6，自动检查打包后程序中的 Python、NAOqi SDK 和 Tk，再生成含配置与操作文档的 ZIP。发布时可将 ZIP 作为仓库 Release 附件；`build/`、`dist/` 和 `release/` 不进入源码版本管理。

当前版本已完成压缩包解压、EXE 校验及清空 Python / Conda / SDK 环境变量后的内置组件加载检查。此检查不连接机器人，不代替不同电脑和机器人上的实机验收。

重新分发时需核对厂家 SDK 及第三方组件的许可要求。

<a id="structure"></a>

## 项目结构

```text
.
├── nao_gui.py                 GUI 入口与打包运行环境
├── nao_diagnostic.py          命令行入口
├── analyze_nao_logs.py        离线日志分析入口
├── nao_diag/
│   ├── gui.py                桌面界面
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
│   └── checks/
│       ├── automatic.py      自动数据检查
│       ├── guided.py         触摸、按键与灯光检查
│       ├── motion.py         运动检查与保护
│       └── common.py         采样、统计与图像处理
├── scripts/runtime.ps1        Python 与 SDK 环境查找
├── packaging/                 发布包使用说明
├── docs/                      现场操作与阈值文档
├── run_gui.bat                启动 GUI
├── run.bat                    启动命令行
├── build_exe.bat              构建 EXE 与 ZIP
├── nao_toolbox.spec           打包配置
├── config.example.json        阈值配置示例
└── robots.example.csv         批量机器人清单示例
```

<a id="faq"></a>

## 关于 CRA

本项目用于 CCU 机器人协会的设备维护、功能验收与机器人项目开发。复测时请记录机器人型号、NAOqi 版本、配置和报告；反馈问题时附上对应项目的错误摘要与日志。

[CCU Robotics Association](https://github.com/CCU-Robotics-Association) · [协会官网](https://ccu-robotics-association.github.io/)

---

<div align="center">

**CRA NAO Toolbox**

<sub>CCU · ROBOTICS · ASSOCIATION</sub>

</div>

