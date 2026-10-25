<!--
作者 / Author: XCrane
-->

<div align="center">

<a href="https://github.com/CCU-Robotics-Association">
  <img src="https://raw.githubusercontent.com/CCU-Robotics-Association/.github/main/profile/assets/logo.svg" width="132" alt="CCU Robotics Association Logo">
</a>

# CCU Robotics Association

### NAO 机器人刷机教程 · NAO Flashing Guide

CCU 机器人协会 · 2026 —— Future

[![Organization](https://img.shields.io/badge/CCU-Robotics_Association-4C1D95?style=flat-square&labelColor=181717&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4KPHN2ZyB3aWR0aD0iNTAxIiBoZWlnaHQ9IjQ3MCIgdmlld0JveD0iMCAwIDUwMSA0NzAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI%2BCiAgPHBhdGggZD0iTSA4OSA5NSBMIDAgNDY5IEwgNDQyIDQ2OSBMIDQ1MCA0MTQgTCAzMTkgMjMwIEwgMjQxIDIzMCBMIDM2OCA0MTEgTCA3MyA0MTAgTCAxNDkgOTcgWiBNIDExMSAxIEwgOTkgNTMgTCA0NDQgNTMgTCA0NDQgNjYgTCA0MjggMTYxIEwgNDc3IDIyNSBMIDUwMCAwIFoiIGZpbGw9IndoaXRlIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiLz4KPC9zdmc%2BCg%3D%3D)](https://github.com/CCU-Robotics-Association)
![Flasher](https://img.shields.io/badge/Flasher_2.1.0.19-ffffff?style=flat-square)
![NAOqi](https://img.shields.io/badge/NAOqi_2.8.7.4-ffffff?style=flat-square)

[**官网(Website) »**](https://ccu-robotics-association.github.io/) | [**GitHub 主页 »**](https://github.com/CCU-Robotics-Association) | [**NAO 项目(Project) »**](https://github.com/CCU-Robotics-Association/CRA-NAO)

> **一  同  奋  进  前  行  ，  共  就  非  凡  之  事**

</div>

---

使用 **Flasher** 将系统镜像写入 U 盘，再通过 U 盘完成 NAO 系统重装或恢复出厂设置

> [!IMPORTANT]
> 本页适用于 **NAO V6 + NAOqi 2.8.7.4**，使用仓库内的 Windows 64 位 Flasher 工具包

## <img src="./assets/icons/compass.svg" width="22" height="22" alt=""> Navigation | 导航

[文件下载](#downloads) · [操作准备](#preparation) · [制作 U 盘](#usb) · [机器人刷机](#flashing) · [完成检查](#verification) · [常见问题](#faq)

<a name="downloads"></a>

## <img src="./assets/icons/download.svg" width="22" height="22" alt=""> Downloads | 文件下载

| 文件 | 用途 | 获取方式 |
| :--- | :--- | :---: |
| `flasher-2.1.0.19-win64-vs2010.zip` | Windows 64 位 Flasher 工具包 | [下载工具](https://github.com/CCU-Robotics-Association/CRA-NAO/raw/refs/heads/main/Flasher/flasher-2.1.0.19-win64-vs2010.zip) |
| `2.8.7.4_20210820_094013.opn` | NAOqi 2.8.7.4 系统镜像 | [镜像文件](./2.8.7.4_20210820_094013.opn) |

打开镜像文件页面后，使用页面中的下载按钮获取完整镜像

> [!NOTE]
> 镜像通过 Git LFS 存储，完整大小为 **731,909,120 字节**。如果下载结果只有约 134 字节，或内容以 `version https://git-lfs.github.com/spec/v1` 开头，拿到的是指针文件，不能用于刷机

<details>
<summary><strong>镜像校验与 Git LFS 下载</strong></summary>

镜像 SHA256：

```text
d82e5dd221712555f20c430f3ebcbe46825d5179f1bc0e2594629489855e24a4
```

在镜像所在目录打开 PowerShell，计算 SHA256，并与上面的值逐字核对：

```powershell
Get-FileHash .\2.8.7.4_20210820_094013.opn -Algorithm SHA256
```

如果通过 Git 克隆仓库，安装 Git LFS 后，在仓库根目录执行以下命令下载本页镜像：

```bash
git lfs install --local
git lfs pull --include="Flasher/2.8.7.4_20210820_094013.opn"
```

</details>

<a name="preparation"></a>

## <img src="./assets/icons/wrench.svg" width="22" height="22" alt=""> Preparation | 操作准备

- 核对机器人型号与镜像版本，确认操作对象为 NAO V6
- 备份 U 盘内的资料，以及需要保留的机器人程序、数据和配置
- 确认机器人电池电量充足，备好充电器与网线
- 将 ZIP 完整解压，保留 `flasher.bat`、`bin`、`lib` 和 `share` 的相对位置

> [!CAUTION]
> 制作刷机 U 盘会覆盖目标 U 盘的数据；勾选 `Factory Reset` 后刷机会清空机器人的用户数据并重置设置，操作前务必完成备份

<a name="usb"></a>

## <img src="./assets/icons/hard-drive.svg" width="22" height="22" alt=""> USB Preparation | 制作刷机 U 盘

1. **连接 U 盘**：插入目标 U 盘，核对容量与设备信息，暂时拔掉其他移动硬盘
2. **启动工具**：在解压目录中右键 `flasher.bat`，选择“以管理员身份运行”
3. **选择镜像**：点击 `Browse`，选择已经校验的 `.opn` 文件
4. **选择设备**：在设备列表中选中目标 U 盘，未显示时点击 `Refresh`
5. **选择重置方式**：需要清空用户数据并恢复出厂设置时勾选 `Factory Reset`，无需恢复出厂设置时不勾选
6. **写入镜像**：再次核对镜像与目标 U 盘，点击 `Write`，等待工具明确提示完成
7. **弹出 U 盘**：写入完成后安全弹出 U 盘

> [!NOTE]
> 写入后 Windows 可能提示“需要格式化磁盘”，请选择取消，再次格式化会破坏刚制作的刷机 U 盘

<a name="flashing"></a>

## <img src="./assets/icons/bot.svg" width="22" height="22" alt=""> Flashing | 启动机器人刷机

| 阶段 | 操作与确认 |
| :---: | :--- |
| **关机** | 正常关闭 NAO，确认机器人已关机 |
| **接入** | 将制好的 U 盘插入头部后方 USB 接口，确认机器人放置稳妥且电量充足 |
| **启动** | 按住胸前按钮，直至胸灯快速闪蓝后松开 |
| **等待** | 等待系统升级，头部和耳部灯光会随阶段变化 |
| **确认** | 听到启动及升级结果提示后，按一次胸前按钮听取通知，核对更新结果与版本号 |

> [!WARNING]
> 刷机过程中不要拔出 U 盘、强制关机或断电，不要仅凭灯光变化判断刷机已经结束

<a name="verification"></a>

## <img src="./assets/icons/circle-check.svg" width="22" height="22" alt=""> Verification | 完成检查

- 检查机器人能否正常启动，是否播报系统更新成功
- 检查版本提示是否与目标镜像 `2.8.7.4` 一致
- 使用 `Factory Reset` 后，检查是否完成恢复出厂设置，并重新配置所需网络与项目环境
- 将刷机结果与后续硬件检查分别记录

需要检查送修后的功能状态时，参见 [NAO 机器人验修工具箱](../NAO_inspection_repair/README.md)

<a name="faq"></a>

## <img src="./assets/icons/circle-dot.svg" width="22" height="22" alt=""> FAQ | 常见问题

<details>
<summary><strong>下载到的镜像只有约 134 字节</strong></summary>

这是 Git LFS 指针文件。重新从镜像文件页面下载，或使用上面的 `git lfs pull` 命令获取镜像，再核对大小与 SHA256

</details>

<details>
<summary><strong>U 盘没有显示，或提示已有文件系统</strong></summary>

先点击 `Refresh`，并确认 Flasher 以管理员身份运行。若工具要求未格式化的 U 盘，应在备份并确认目标设备后清理该 U 盘的分区，普通格式化不一定满足要求

</details>

<details>
<summary><strong>Windows 提示需要格式化刷机 U 盘</strong></summary>

选择取消，不要格式化。该提示不代表镜像写入失败，应以 Flasher 的完成提示为准

</details>

<details>
<summary><strong>是否必须勾选 Factory Reset</strong></summary>

按操作目的选择，需要清空用户数据并恢复出厂设置时才勾选，不勾选也不能代替提前备份

</details>

## <img src="./assets/icons/book-open.svg" width="22" height="22" alt=""> References | 参考资料

- [RobotLAB：NAO V6 刷机与恢复出厂设置](https://www.robotlab.com/support/factory-reset-nao-robot-flasher/)
- [Aldebaran：NAO 升级指南](https://community-static.aldebaran.com/resources/Tutos/NAO%20Upgrade%20Guide.pdf)

---

<div align="center">

### CCU · ROBOTICS · ASSOCIATION

<sub>NAO 机器人刷机教程 | CRA NAO</sub>

[**官网(Website)**](https://ccu-robotics-association.github.io/) · [**GitHub 主页**](https://github.com/CCU-Robotics-Association) · [**NAO 项目(Project)**](https://github.com/CCU-Robotics-Association/CRA-NAO)

<sub>CCU Robotics Association</sub>

</div>
