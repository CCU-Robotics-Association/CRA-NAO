<!--
@ Project            : NAO 机器人验修工具箱
@ Description        : Linux、macOS 启动、构建与兼容范围
@ Author             : XCrane
-->

# Linux 与 macOS

NAOqi 2.8 的 Python SDK 包含平台相关原生库。Windows、Linux 和 macOS 必须分别使用对应 SDK 构建。

## 源码运行

安装带 Tk 的 64 位 Python 2.7，取得厂家对应系统的 pynaoqi 2.8.6 SDK，然后设置：

```sh
export PYTHON_EXE=/path/to/python2.7
export PYNAOQI_SDK=/path/to/pynaoqi-sdk
sh run_gui.sh
```

命令行验收：

```sh
sh run.sh --ip 192.168.1.101 --robot-id 01 --profile guided
```

Mac 也提供 `run_gui.command`。从 Finder 启动时，需要先配置好 SDK 与 Python 环境；从终端执行 `sh run_gui.sh` 可直接查看环境错误。

不需要更改系统安全设置。不要关闭 SIP 或修改系统 Python 来迁就旧 SDK。

## 原生包构建

在目标系统中设置上述环境变量，再执行：

```sh
"$PYTHON_EXE" -m pip --isolated install --require-hashes --no-deps -r packaging/requirements-bootstrap.lock
"$PYTHON_EXE" -m pip --isolated install --require-hashes --no-deps --no-build-isolation --no-use-pep517 -r requirements-build.txt
sh build_unix.sh
```

构建程序将检查打包后的 Python、SDK 与 Tk，并生成 `release/NAO_Toolbox-<版本>-<系统>-x86_64.tar.gz`。检查失败时不生成发布包。
每个压缩包同时生成 `.sha256` 和 `.build.json`，记录摘要、实际构建工具版本和来源提交。发布前的校验步骤见 [构建与发布校验](BUILD_SECURITY.md)。

Linux 无图形会话的构建环境需安装 Xvfb，并通过 `xvfb-run -a sh build_unix.sh` 执行。运行成品仍需图形桌面及系统桌面库。
中文界面需要系统具备中文字体；Ubuntu 可安装 `fonts-noto-cjk`。

仓库根目录的 GitHub Actions 工作流分别使用 Ubuntu 22.04 与 Intel macOS 15 构建，下载厂家 SDK 和独立 Python 2.7 环境。`packaging/github-native-build.yml` 保留工作流模板。

## 架构与验证范围

- Linux 目标为 x86_64。构建环境为 Ubuntu 22.04，不承诺向更旧 glibc 系统兼容。
- macOS 目标为 Intel x86_64，构建环境为 macOS 15。
- M 系列不是旧 SDK 的原生构建目标，通过 Rosetta 运行的方式需要单独验证。
- macOS 包未进行 Developer ID 签名或 Apple 公证。
- 内置组件检查不连接机器人，不能代替机型、固件和现场功能验收。

GUI 会按系统选择字体，并使用 Windows 默认程序、macOS `open` 或 Linux `xdg-open` 打开报告。
成品默认报告目录为 `~/Documents/NAO_Reports`，可在界面修改。

启动错误日志：

| 系统 | 路径 |
| --- | --- |
| Linux | `${XDG_STATE_HOME:-~/.local/state}/NAO_Toolbox/gui_error.log` |
| macOS | `~/Library/Logs/NAO_Toolbox/gui_error.log` |
