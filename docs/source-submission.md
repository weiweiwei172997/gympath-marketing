# 课程源码包

本次源码交付约定为 `artifacts/GymPath-BA4043-Source.zip`，包内只有一个
`gympath-marketing/` 根目录。它包含四个原生 HTML、共享 CSS、三个浏览器
JavaScript、自制 SVG、独立后端、可选 WSGI 适配器、三份依赖清单、独立环境解析的
运行依赖锁文件、启动脚本、
回归测试、运行与安全说明、代码及资源来源说明和 `README-SUBMISSION.md`。

此包是网站代码交付，不是英文 Word 报告，也不会补造真实研究或成员分工。
旧 `gympath-pythonanywhere.zip` 是较小的托管运行包，两者用途不同。

## 构建及核验

在项目根目录运行：

```text
python scripts/build-submission-package.py
python scripts/verify-submission-package.py
```

完整核验需要先安装 `requirements-test.txt` 和 `requirements-deploy.txt`。
ZIP 采用逐文件显式白名单，不递归收集整个工作目录。新增运行或测试文件后，
必须先审查并更新白名单，再重建和核验。

每个文件的路径、大小和 SHA256 记录在包内 `SUBMISSION-MANIFEST.json`，
同时输出外部 `GymPath-BA4043-Source-manifest.json` 和
`GymPath-BA4043-Source.sha256`。条目顺序、时间和权限固定，不写构建时间；
在同一 Python/zlib 环境中相同源码得到相同 ZIP。包的最终大小与哈希以这些
实际生成的文件为准，不在本文提前写入数字。

核验器检查单根目录、重复条目、路径穿越、符号链接、白名单完整性、逐文件
哈希和外部 ZIP 校验值；随后临时解压，使用解压后代码与全新临时数据库
执行公开页面、游客生成、注册、保存、CSRF/同源拒绝、账号隔离、退出重登和
数据库持久性检查。静态模式另起仅绑定 127.0.0.1 的临时 HTTP 服务，检查
四页及资源、后端缺失状态及禁用的无脚本表单。它不会读取正在使用的数据库
或执行公网压力/攻击测试，也不是完整浏览器或手机交互验收。

## 排除项和事实边界

- `.env`、私钥、凭证、Cookie、token、运行数据库、数据目录、日志、工具依赖、
  虚拟环境、缓存、用户照片及手机账号截图均排除。
- 仅收录本站运行与验收所需源码，以及训练规则的来源 manifest。
- 不包含平台专用配置、运行状态 JSON、测试账号 fixture、托管截图或手机信息。
- 历史设计与内部交接记录不纳入提交包；运行方式以包内 README 为准。教学视频
  元数据核验不等于逐项播放；打印样式检查不等于实际分页验收。
- 安全修复范围和局限见 `security-hardening.md`；不能承诺网站绝对不会被攻击。

检查报告写入 `artifacts/GymPath-BA4043-Source-validation.json`。该报告是构建后的
外部证据，不把包含当前 ZIP 哈希的报告再嵌入 ZIP，以免产生自引用哈希。
