<!--
@ Project            : CRA-NAO
@ Description        : NAO USB 刷机与恢复出厂操作说明
@ Author             : XCrane
-->

# NAO 刷机说明

使用 NAO Flasher 将系统镜像写入 U 盘，再通过 U 盘为 NAO 重装系统或恢复出厂设置。以下以 Windows 操作为例。

> 写入镜像会清空所选 U 盘；勾选 `Factory Reset` 会清除机器人用户数据和设置。开始前先备份，并确认选中的磁盘确实是 U 盘。

## 一、准备文件和设备

本目录中的文件：

| 文件 | 用途 |
| --- | --- |
| `flasher-2.1.0.19-win64-vs2010.zip` | Windows 64 位刷机工具 |
| `2.8.7.4_20210820_094013.opn` | NAOqi 2.8.7.4 系统镜像，面向 NAO V6 |

**当前仓库中的 Flasher ZIP 只有 2 字节，并非有效压缩包，暂时不能使用。** 请先通过设备供应商提供的渠道取得完整工具包；目录补齐工具前，不要把解压失败当作电脑环境问题。

本镜像对应 NAO V6，不要直接用于 V4、V5 或 Pepper。先根据设备型号确认镜像适配关系，不能只看机器人外壳颜色。[V6 镜像与刷机说明](https://www.robotlab.com/support/factory-reset-nao-robot-flasher/)

还需准备空闲 U 盘、机器人充电器和网线。备份机器人上的程序、数据及网络配置；电池充满，在平整地面留出足够空间，避免升级后的启动动作造成跌落。

### 下载完整镜像

`.opn` 使用 Git LFS 保存。若下载到的文件只有约 134 字节，内容以 `version https://git-lfs.github.com/spec/v1` 开头，那只是指针，不能刷机。[Git LFS 说明](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage)

可在镜像文件的 GitHub 页面使用下载按钮获取完整文件；使用 Git 克隆的用户，也可在仓库根目录执行：

```sh
git lfs install --local
git lfs pull --include="Flasher/2.8.7.4_20210820_094013.opn"
```

需要事先安装 Git LFS。当前仓库记录的完整镜像大小为 **731,909,120 字节**，SHA256 为：

```text
d82e5dd221712555f20c430f3ebcbe46825d5179f1bc0e2594629489855e24a4
```

Windows PowerShell 中可核对：

```powershell
Get-FileHash .\2.8.7.4_20210820_094013.opn -Algorithm SHA256
```

此摘要用于比对仓库中的镜像对象，不代表已经验证厂家数字签名。

## 二、制作刷机 U 盘

1. 将完整的 Flasher 工具包解压到本地文件夹，不要直接在压缩包内运行。
2. 插入已备份、容量足以写入镜像的 U 盘，暂时拔掉其他不需要的移动硬盘，避免选错。
3. 右键刷机工具的 `flasher.bat` 或工具包提供的启动入口，选择“以管理员身份运行”。
4. 点击 `Browse`，选择完整的 `.opn` 镜像。
5. 在设备列表中选择目标 U 盘，核对容量和设备信息；未显示时点击 `Refresh`。
6. 需要完全重置机器人时勾选 `Factory Reset`；这会删除用户数据并重置网络等设置。不勾选也应先备份。
7. 点击 `Write`，等待工具明确提示写入完成，再安全弹出 U 盘。

如果 Flasher 提示 U 盘已有文件系统，需按工具要求清理该 U 盘的分区。先确认设备身份，再参考厂商文档处理；不熟悉磁盘操作时请找有经验的成员协助，不要对不确定的磁盘执行清盘命令。写入后 Windows 可能提示格式化 U 盘，选择取消，不要再次格式化。[NAOFlasher 制盘说明](https://fileadmin.cs.lth.se/robot/nao/doc/software/naoflasher/naoflasher.html)

## 三、启动机器人刷机

1. 将 NAO 正常关机，确认灯光熄灭后，把制好的 U 盘插入头部后方 USB 接口。
2. 确认机器人放置稳妥、电池充足，保持可靠供电；不要拿在手上或放在桌边升级。
3. 按住胸前按钮，直到胸灯快速闪蓝后松开。V6 操作说明为至少约 6 秒，以实际指示和对应机型说明为准。
4. 等待升级，期间头部、耳部灯光会变化。不要拔 U 盘、强制关机或随意断电；不能仅凭等待时间判断已经完成。
5. 听到启动及升级结果提示后，按一次胸前按钮听取通知，确认系统更新成功及版本号；选择了恢复出厂时，还应确认重置成功的通知。

V6 的刷机过程可能需要约 10～30 分钟。若长期无进展或反复报错，记录灯光、语音及镜像信息，先查明原因，不要连续强制断电重试。[V6 启动与完成提示](https://www.robotlab.com/support/factory-reset-nao-robot-flasher/)

## 四、刷机后检查

- 按设备提示完成自检；需要站立或校准时，将机器人放在空旷、防滑地面并全程看护，不要推拉测试保护功能。
- 确认升级结束后再取出 U 盘，并关好头部接口盖。
- 恢复出厂后，先通过网线重新连接，配置网络和账户，检查实际 NAOqi 版本。
- 确认跌倒、碰撞等安全保护可用，再进行关节、行走等主动测试。系统成功启动不等于硬件已经修好。[升级后检查说明](https://fileadmin.cs.lth.se/robot/nao/doc/embedded/upgrade.html)

需要做送修后的功能验收，可使用仓库中的 [NAO 机器人验修工具箱](../NAO_inspection_repair/)。刷机操作与功能验收应分开记录。
