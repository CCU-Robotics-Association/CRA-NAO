# NAO 机器人维修验收工具

这是一个面向批量送修回机的 NAO 功能验收项目。它在电脑端通过 NAOqi 连接机器人，按顺序完成自动数据检查、引导式人工检查和可选运动检查；每个通过的项目可由机器人语音播报，并输出 JSON、CSV、HTML、相机图像、原始采样和运行日志。

当前电脑已经具备可用环境，启动器会自动使用：

- Conda 环境 `NAO`：Python 2.7.18，64 位；
- pynaoqi SDK：2.8.6.23，Win64；
- SDK 实际路径 `P:\NAO\nao\pynaoqi-python2.7-2.8.6.23-win64-vs2015-20191127_152649\pynaoqi-python2.7-2.8.6.23-win64-vs2015-20191127_152649\lib`。

现有 Conda 的用户级 `requests/urllib3` 有冲突，且 `naoqi_sdk.pth` 指向旧目录。`run.bat` / `run.ps1` 会只为本次进程禁用用户 site 并注入正确 SDK 路径，不修改全局环境。

如果换到没有 `NAO` 环境的电脑，可先运行 `conda env create -f environment.yml`；启动器不会自动创建环境。pynaoqi 仍需从厂家渠道单独安装，并用 `-SdkRoot` 指向与机器人 NAOqi 主版本及系统位数匹配的 SDK。Windows 建议从 `run.bat` 进入，避免本机 PowerShell 执行策略阻止 `.ps1`。

## 最快开始

机器人开机并与电脑处于同一网络后，在本目录运行：

```bat
run.bat -Ip 10.32.176.49 -RobotId NAO-001 -Profile guided
```

`guided` 是录制验收视频时推荐的模式：机器人会逐项播报，引导操作者在头部、左手和右手各任意触摸一次，短按胸键，按四个脚部开关，观察 LED，听测试音，并确认相机画质。它不会驱动关节或行走。

只做无人值守数据快检：

```bat
run.bat -Ip 10.32.176.49 -RobotId NAO-001 -Profile quick -NoVoice
```

`-NoVoice` 只关闭验收播报；音频通路测试仍会播放约 1.4 秒的 1 kHz 短音。如现场必须静音，再加 `-Skip audio`。

先检查本机启动环境和测试清单：

```bat
run.bat -ListTests
run.bat -DemoReport
```

示例报告会生成在 `reports\DEMO\...\report.html`。

## 三种测试模式

| 模式 | 内容 | 会让机器人动作吗 | 适用场景 |
|---|---|---:|---|
| `quick` | 网络、版本、服务、内置诊断、电池、板卡、温度、静态关节、IMU、FSR、声纳、双相机、音频通路；可选原生日志 | 否；会播放短测试音 | 批量无人值守初筛 |
| `guided` | `quick` + 头部/左手/右手整体触摸、胸键、四个脚部开关、LED，以及声光画面人工确认 | 否 | 录像留证和完整的非运动验收 |
| `full` | `guided` + 可选小幅关节运动 + 可选短距离行走 | 只有显式解锁后 | 维修支架和安全场地上的最终验收 |

状态含义：

- `PASS`：自动条件以及该项目要求的人工确认均通过；
- `WARN`：数据可用但存在边界值，或画质/音质/容量等尚未完成人工或标准设备确认；
- `FAIL`：明确诊断错误、数据缺失/异常或人工确认失败；
- `SKIP`：硬件/API 不存在，未授权，或安全前置条件不满足；
- `ERROR`：测试程序或 NAOqi 调用发生未处理异常。

总判定为 `ACCEPT`、`ACCEPT_WITH_NOTES` 或 `REJECT`。只要有 `WARN/SKIP`，就不会生成无条件的“整机完全通过”结论。

## 测试覆盖

- 网络与系统：TCP 9559、5 次 RPC 延迟、机器人名、型号配置、NAOqi 版本、Autonomous Life 状态；
- NAOqi 服务：运行时能力探测，不按单一机型硬编码；
- 官方诊断：`ALDiagnosis` 主动/被动诊断摘要、`Diagnosis/*` 键、温度诊断、系统通知；
- 电池：电量、原始电流/温度/状态和诊断键；单次快照不会冒充容量测试；
- 板卡：动态发现 Ack/Nack 计数器，观察增量；
- 关节：实际关节列表、命令角/传感角/刚度、温度和 `ALMotion.getSummary()`；
- IMU：兼容新旧键名，连续采样加速度、陀螺仪和倾角；
- FSR：双脚各四点压力与左右/总读数；
- 声纳：订阅后采样左右距离；交互模式建议放置约 0.40 m 的平面标靶；
- 相机：上下相机各取 3 帧，检查尺寸、亮度、对比度、时间戳，并保存 BMP；
- 音频：四路麦克风安静基线、1 kHz 测试音回录和人工听音确认；
- 触摸/按键：头部、左手、右手各任选一个触摸位置，按区域验证完整的 `0 → 1 → 0` 按下释放周期；不再要求逐片测试；
- LED：眼睛 RGB、胸灯、双脚灯、双耳蓝灯循环和人工坏点确认；
- 运动：在支架上按实际限位进行安全范围内的小幅关节跟踪并回位，记录目标、实测、误差、电流和温度；
- 行走：低速短距离前行，连续采样倾角与 FSR、持续比较跌倒事件时间戳，并记录行走前后里程计；
- 日志：本程序的 `run.log` 固定保存；只有提供 `-CollectLogs` 或 `-LogDir` 时才加入日志分析项目，可选 SSH 读取当前启动 journal 和常见 NAOqi/HAL/LoLA 日志并生成关键词证据摘要。

## 安全门控

默认命令永远不会驱动关节或行走。

### 支架上的关节测试

必须使用可靠的维修支架，清空周围硬物、线缆和人员，并由操作者全程看护：

```bat
run.bat -Ip 10.32.176.49 -RobotId NAO-001 -Profile full -AllowMotion
```

程序要求本次流程中的电池、温度和静态关节项目均为 `PASS`，并要求输入 `MOVE`。诊断采用失效安全分类：关节、电机、电池、温度、IMU、FSR、跌倒/碰撞保护及无法识别的故障会阻止运动；明确属于相机、音频、声纳、触摸、脚部碰撞开关或 LED 的故障仍记为整机 `FAIL`，但不会阻止继续检查关节。随后程序会重新读取电池、诊断、全部关节温度/角度，确认 Autonomous Life 已进入 `disabled`，并验证跌倒、自碰撞、外部碰撞和诊断保护均已开启。任何运动相关数据缺失、状态变化、跟踪异常、过温或通信异常都会停止后续关节。测试前先缓慢释放全身刚度，每个关节以最新传感角为基准缓升到受限刚度，结束时验证全身刚度为 0。`LHipYawPitch` 与 `RHipYawPitch` 是同一物理机构，只驱动一次。

### 地面行走测试

先完成支架关节测试，把机器人移到平整防滑地面，拔掉电源线，保证前方至少 2 m、四周至少 1 m 无障碍；一人看护机器人，另一人监控控制电脑和现场断能装置。`Ctrl+C` 只是软件/网络层的最佳努力停止，胸键长按是延迟关机流程，两者都不是安全级即时急停：

```bat
run.bat -Ip 10.32.176.49 -RobotId NAO-001 -Profile full -AllowMotion -AllowWalk
```

程序会额外要求现场操作者手动输入 `WALK-NAO-001`。行走还要求同一 `full` 流程中的关节运动和 IMU 为 `PASS`、FSR 数据完整；先确认没有既有运动任务/Body 资源占用，并在任何动作前显式启用脚接触与腿部刚度保护。`wakeUp` 本身会驱动全身，程序使用异步任务全程监控其超时、双脚 FSR、IMU、全身温度和跌倒事件时间戳；只有准确到达 `StandInit` 才继续，不会再无条件发送第二次站立姿态。

行走前会读取 `ALMotion.getMass("Body")`，以机器人模型质量动态计算稳定总承重上下限和单脚下限，并在 `wakeUp` 前、结束后分别连续采样。行走中持续监控双脚 FSR、IMU、跌倒事件和全身温度；停止时先请求平衡减速，只有无法停止才升级取消任务。只有行走完成且最终稳定性复核通过，程序才依次异步监控进入 `Crouch` 和执行 `rest()`；中止、跌倒或状态不明时不会再发送新姿态命令，必须由操作者扶稳并处理。不要通过推倒、阻挡关节或制造碰撞来测试保护功能。

任何已经进入运动会话的测试结束后，Autonomous Life 都保持 `disabled`，程序不会自动恢复。请在机器人回到安全区域、姿态和故障状态均已人工确认后再手动恢复。

`-AssumeYes` 只能旁路支架关节测试的 `MOVE` 口令和等待停顿，不能替代相机、音频、LED、行走质量等人工确认，也禁止与 `-AllowWalk` 同时使用。它只适用于具备可靠机械固定、隔离区和现场断能流程的专用测试台，不适合正式录像验收。`-NonInteractive` 无法输入安全口令，主动运动会安全跳过。

详细现场步骤见 [docs/OPERATOR_CHECKLIST.md](docs/OPERATOR_CHECKLIST.md)。

## 批量检查

复制示例清单并填写每台机器人：

```bat
copy robots.example.csv robots.csv
run.bat -Inventory robots.csv -Profile quick
```

CSV 列：

```text
robot_id,ip,port,notes,enabled
NAO-001,192.168.1.101,9559,第一批,1
```

交互式批量录像也可使用 `-Profile guided`，程序会一台一台引导。批量主动运动风险较高；任一运动项目失败或异常时，程序会停止本批次，必须先人工处置该机器人再重新启动。行走不能使用 `-AssumeYes`。

## 日志采集与离线分析

稳定 API 数据（`ALDiagnosis`、系统通知、传感器、程序异常）每次都会保存。原生系统日志需要机器人已经授权 SSH；项目不接收命令行密码，推荐密钥：

```bat
run.bat -Ip 10.32.176.49 -Profile guided -CollectLogs -SshKey C:\Keys\nao_ed25519
```

仅分析已有日志：

```bat
C:\Users\12550\.conda\envs\NAO\python.exe analyze_nao_logs.py P:\已有日志目录 --output log-analysis.json
```

日志文本格式不是稳定 API，关键词命中只作辅助证据；最终结论应优先看 `ALDiagnosis`、原始传感器数据和人工复核。

## 报告结构

每台机器、每次运行都会生成独立目录：

```text
reports/<robot-id>/<时间>_<ip>/
  report.html                 离线可打开的汇总报告
  report.json                 完整机器可读结果、阈值和原始指标
  tests.csv                   每个测试一行
  metrics.csv                 展平后的所有测量值
  run.log                     本工具执行日志
  artifacts/
    diagnosis_snapshot.json
    joint_temperatures.json
    joint_static_snapshot.json
    almotion_summary.txt
    imu_samples.json
    sonar_samples.json
    camera_top.bmp
    camera_bottom.bmp
    audio_energy.json
    ...
  robot_logs/                 可选 SSH 原生日志
```

Python 主程序退出码：`0=全部执行项通过`，`1=有 WARN/SKIP`，`2=FAIL/ERROR 或参数/配置拒绝`，`3=批次启动异常`，`4=Python 已启动但无法导入 pynaoqi`。若 `run.bat` 在进入 Python 前就找不到 Python 2.7 或 SDK，PowerShell 启动层通常返回 `1` 并显示原因。

## 配置阈值

复制 [config.example.json](config.example.json) 后通过 `-Config` 使用：

```bat
copy config.example.json config.local.json
run.bat -Ip 10.32.176.49 -Profile guided -Config config.local.json
```

项目内阈值是保守的工程初值，不是厂家维修认证标准。安全相关覆盖有不可越过的硬边界；例如运动最低电量不得低于 40%、温度预警只能在 35–55°C、关节刚度最多 0.50、关节幅度最多 0.15 rad、步距最多 0.20 m、步频比例最多 0.35。稳定站立 FSR 还同时受模型质量比例约束：默认总量为 `0.60–1.40 × Body 质量`，单脚至少为 `0.12 × Body 质量`，且与绝对 kg 门槛取更严格者。超界配置会在连接机器人前被拒绝。正式批量验收前，应使用同型号、同固件的 3–5 台已知良机各重复至少 3 次，建立关节电流/误差、温升、相机、音频、电池压降和声纳的本地基线，再在安全边界内收紧配置。完整说明见 [docs/THRESHOLDS.md](docs/THRESHOLDS.md)。

## 版本兼容性

当前 pynaoqi 2.8.6 环境适合 NAO V6 / NAOqi 2.8。NAO V4/V5 通常使用 NAOqi 2.1，应安装与机器人主版本、Windows 位数相匹配的官方 SDK 和 Python 2.7，然后用：

```bat
run.bat -PythonExe C:\path\to\python.exe -SdkRoot C:\path\to\pynaoqi -Ip 192.168.1.10
```

代码会动态发现服务、关节和新旧 IMU 键，但 SDK 二进制本身仍必须匹配。不要使用来源不明的 `pip install naoqi` 包。

官方参考：

- [pynaoqi 2.8 安装](https://doc.aldebaran.com/2-8/dev/python/install_guide.html)
- [ALDiagnosis](https://doc.aldebaran.com/2-8/naoqi/diagnosis/aldiagnosis.html)
- [ALMotion](https://doc.aldebaran.com/2-8/naoqi/motion/almotion.html)
- [ALMotion 任务与资源](https://doc.aldebaran.com/2-8/naoqi/motion/tools-motion-task-api.html)
- [ALMotion 质量与通用工具](https://doc.aldebaran.com/2-8/naoqi/motion/tools-general-api.html)
- [跌倒管理器事件](https://doc.aldebaran.com/2-8/naoqi/motion/reflexes-fall-manager-api.html)
- [ALMemory 与传感器](https://doc.aldebaran.com/2-8/naoqi/core/almemory-api.html)
- [相机 API](https://doc.aldebaran.com/2-8/naoqi/vision/alvideodevice-api.html)
- [音频 API](https://doc.aldebaran.com/2-8/naoqi/audio/alaudiodevice-api.html)
- [V6 声纳规格](https://doc.aldebaran.com/2-8/family/nao_technical/sonar_naov6.html)
- [LED API](https://doc.aldebaran.com/2-8/naoqi/sensors/alleds-api.html)

## 开发验证

项目无第三方运行时依赖（pynaoqi 除外）。运行单元测试：

```bat
C:\Users\12550\.conda\envs\NAO\python.exe -B -m unittest discover -v
```

纯逻辑模块也兼容 Python 3，便于在没有机器人 SDK 的电脑上生成示例报告和测试日志分析。

