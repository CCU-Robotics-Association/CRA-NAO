<!--
@ Project            : NAO 机器人验修工具箱
@ Description        : 构建输入、发布摘要和来源证明的核验方法
@ Author             : XCrane
-->

# 构建与发布校验

本流程校验构建输入和产物来源，不表示厂家 SDK 没有漏洞，也不替代 Windows 代码签名或 Apple 公证。已公开的旧版本不会因更新构建脚本而自动获得这些保障。

## 构建输入

CI 先用系统 Python 3 执行 `scripts/fetch_build_inputs.py`，再安装旧版 Python。下载只允许清单内的 HTTPS 来源；文件大小或固定 SHA256 不一致时立即退出，不运行安装器或解压 SDK。已有缓存也必须重新校验。

`packaging/build-inputs.json` 固定 Python 和 SDK 下载地址、大小及 SHA256。Miniconda 摘要已与 Anaconda 官方下载目录交叉核对；SDK 与 macOS Python 的 SHA256 来自 2026-10-23 对官方 HTTPS 下载内容的计算。这是固定的完整性基线，不是对厂家签名的验证。更新版本时应人工审查来源及摘要，不能从同一次构建下载结果自动刷新清单。

Python 包使用 `packaging/requirements-bootstrap.lock` 和 `requirements-build.txt`，固定直接及传递依赖版本、发行文件 SHA256。安装使用 `--require-hashes --no-deps`，禁用隐式依赖安装及独立构建环境，避免构建过程偷偷拉取未锁定依赖。旧版 PyInstaller、future 和 pefile 只能使用已锁定的源码发行包，不能声称本流程完全没有源码构建。

本地打包应使用专用环境，先安装两个锁文件，再构建。仅核对已安装包版本不能证明这些包最初来自可信发行文件；不要复用来源不明的环境。Windows 当前使用本地已有 Python/SDK，记录明确标为 `local-environment-not-vendor-verified`，不冒充 CI 的下载校验。

## Actions 权限与来源证明

工作流只允许手动触发。所有引用的 Actions 固定到完整提交 SHA；检出后不保留 Git 凭据。构建任务只有仓库只读权限，不持有发布或签名证书。

两个平台的构建与内置组件自检都通过后，独立任务才使用 GitHub OIDC 生成构建来源证明，并使用 GitHub CLI 逐项核验仓库、工作流、main 分支及本次提交身份。该任务不执行项目构建脚本，只下载本轮构建产物并证明其摘要；写权限仅为 `attestations: write`，不是仓库内容写权限。

每个压缩包附带 `.sha256` 和 `.build.json`。后者记录提交、平台、工具版本、锁文件摘要及已校验的输入。来源证明同时覆盖压缩包与这两个附件。Actions 中的 `NAO-build-provenance` 保存证明包。

来源证明建立在 GitHub、仓库维护权限及工作流本身可信的前提上；它证明来源，不证明软件行为无恶意或依赖无漏洞。操作系统桌面库由发行版签名的软件源提供，未固定每个系统包版本，因此本流程也不承诺逐字节可重复构建。

## 下载后核验

在包含压缩包和对应 `.sha256` 的目录中执行：

```sh
# Linux
sha256sum -c NAO_Toolbox-<版本>-linux-x86_64.tar.gz.sha256
# macOS
shasum -a 256 -c NAO_Toolbox-<版本>-macos-x86_64.tar.gz.sha256
```

Windows 使用 `Get-FileHash -Algorithm SHA256 .\NAO_Toolbox-<版本>-win64.zip` 与对应摘要文件比对。摘要文件应从协会官方发布页取得；仅把文件和旁边同样可被篡改的摘要一起下载，不足以验证发布者身份。

对采用新流程生成的 Unix 包，可使用 GitHub CLI 验证来源：

```sh
gh attestation verify <压缩包文件名> --repo CCU-Robotics-Association/CRA-NAO --signer-workflow CCU-Robotics-Association/CRA-NAO/.github/workflows/native-build.yml --source-ref refs/heads/main
```

核验结果中的源码提交必须与准备发布的提交一致。不符合时不要上传或使用，不要关闭校验来继续。旧版 v1.0.0 / v1.1.0 没有该流程生成的来源证明，不能套用这一步并声称已验证。

## 签名边界

目前没有 Windows 代码签名证书和 Apple Developer ID，仍明确保留未签名/临时签名状态。Windows 构建提供 `-RequireSignature`，在没有有效 Authenticode 签名时拒绝生成发布压缩包；这是拒绝开关，不会自动签名。Mac 临时签名仍会做严格校验，但不能当作 Developer ID 签名或公证。

后续取得证书后，再接入受保护的签名任务、可信时间戳及 macOS 公证，并重新验证签名后的成品。不要将证书、私钥、密码写入仓库或聊天，也不要通过关闭系统安全功能来消除告警。
