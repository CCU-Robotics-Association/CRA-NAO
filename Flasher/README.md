<div align="center">

# NAO 机器人刷机教程

### CCU 机器人协会 · NAO 刷机

使用 U 盘完成 NAO 系统重装与恢复出厂设置

![Platform](https://img.shields.io/badge/Platform-Windows-0078D4?style=flat-square)
![Flasher](https://img.shields.io/badge/Flasher-2.1.0.19-555555?style=flat-square)
![NAOqi](https://img.shields.io/badge/NAOqi-2.8.7.4-orange?style=flat-square)

Edited by **XCrane**

[文件下载](#downloads) · [操作准备](#preparation) · [制作 U 盘](#usb) · [机器人刷机](#flashing) · [完成检查](#verification) · [常见问题](#faq)

</div>

---

> [!IMPORTANT]
> 本页围绕 **NAO V6 + NAOqi 2.8.7.4** 说明操作

<a id="downloads"></a>

## 文件下载

| 文件 | 说明 | 获取方式 |
| :--- | :--- | :---: |
| `flasher-2.1.0.19-win64-vs2010.zip` | Flasher 工具包，完整解压后运行 | [下载工具](https://github.com/CCU-Robotics-Association/CRA-NAO/raw/refs/heads/main/Flasher/flasher-2.1.0.19-win64-vs2010.zip) |
| `2.8.7.4_20210820_094013.opn` | NAOqi 2.8.7.4 系统镜像 | [下载镜像](https://media.githubusercontent.com/media/CCU-Robotics-Association/CRA-NAO/main/Flasher/2.8.7.4_20210820_094013.opn) |

镜像由 Git LFS 存储，完整文件大小为 **731,909,120 字节**。如果下载结果只有约 134 字节，或打开后看到 `version https://git-lfs.github.com/spec/v1`，拿到的是指针文件，无法写入 U 盘，尝试重新下载 

<details>
<summary><b>展开：镜像校验与 Git LFS 下载方式</b></summary>

镜像在仓库中记录的 SHA256：

```text
d82e5dd221712555f20c430f3ebcbe46825d5179f1bc0e2594629489855e24a4
```

在镜像所在目录打开 PowerShell，执行：

```powershell
Get-FileHash .\2.8.7.4_20210820_094013.opn -Algorithm SHA256
```

已安装 Git LFS 的用户，可在仓库根目录执行：

```sh
git lfs install --local
git lfs pull --include="Flasher/2.8.7.4_20210820_094013.opn"
```

</details>

<a id="preparation"></a>

## 操作准备

开始前确认：

- 电池电量充足，充电器和网线已备好

<a id="usb"></a>

## 01 · 制作刷机 U 盘

1. **Flasher**： 将 ZIP 完整解压到本地目录，保留 `bin`、`lib`、`share` 与 `flasher.bat` 的相对位置
2. **连接 U 盘**： 暂时拔掉其他移动硬盘，核对目标 U 盘的容量与设备信息
3. **启动 Flasher**： 右键 `flasher.bat`，选择“以管理员身份运行”
4. **选择镜像**： 点击 `Browse`，选择完整的 `.opn` 文件
5. **选择设备**： 在列表中选中目标 U 盘；未显示时点击 `Refresh`
6. **选择重置方式**： 需要完全重装并清空用户数据时勾选 `Factory Reset`
7. **写入并弹出**： 点击 `Write`，等待工具明确提示完成，再安全弹出 U 盘

> [!NOTE]
> 写入后 Windows 可能提示“需要格式化磁盘”，选择取消。再次格式化会破坏刚制作的刷机 U 盘

<a id="flashing"></a>

## 02 · 启动机器人刷机

| 阶段 | 操作与确认 |
| :--- | :--- |
| 关机 | 正常关闭 NAO|
| 接入 | 将制好的 U 盘插入头部后方 USB 接口，确认机器人放置稳妥、电池充足 |
| 启动 | 按住胸前按钮，直至胸灯快速闪蓝后松开。V6 指引为至少约 6 秒|
| 等待 | 头部、耳部灯光会随升级阶段变化，禁止拔 U 盘、强制关机或随意断电 |
| 确认 | 听到启动及升级结果提示后，按一次胸前按钮听取通知，核对更新结果与版本号|

<a id="verification"></a>

## 03 · 检查

系统恢复与硬件验收应分开记录。需要检查送修后的功能状态时，参见 [NAO 机器人验修工具箱](https://github.com/CCU-Robotics-Association/CRA-NAO/tree/main/NAO_inspection_repair)

<a id="faq"></a>

## 常见问题

<details>
<summary><b>U 盘没有显示，或者提示已有文件系统</b></summary>

先刷新设备列表，并确认 Flasher 具有管理员权限。若工具要求未格式化的 U 盘，应在备份后清理该 U 盘的分区；普通格式化不一定满足要求。

</details>

---
