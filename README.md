# GymPath

使用 HTML、CSS、JavaScript 和 FastAPI/SQLite 实现的健身计划网站。

## 功能

- 产品首页：功能介绍、使用步骤和常见问题。
- 训练示例：切换固定计划、展开动作及体验练后反馈。
- 计划试用：根据训练水平、目标、每周次数和单次时间生成计划，无需先注册。
- 账号管理：注册、登录、主动保存计划，以及查看和删除自己的计划。
- 响应式布局和完整计划打印样式。

示例页的反馈表单只在浏览器内演示，不提交、不保存信息。真实计划生成会将四项偏好发送到后端计算；只有登录后主动点击保存，才写入账号数据库。

## 本地运行

需要 Python 3.10 或更新版本。在项目目录执行：

```text
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-runtime.lock
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8081
```

macOS / Linux：

```bash
.venv/bin/python -m pip install -r requirements-runtime.lock
.venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8081
```

打开 <http://127.0.0.1:8081/>，按 `Ctrl+C` 停止服务。

如需只查看产品介绍和固定示例，可直接用浏览器打开 `index.html` 和 `demo.html`，无需安装后端。真实账号和计划生成功能需要运行上述服务。

## 数据与安全

首次使用账号时会创建 `data/gympath.sqlite3`，也可以使用 `GYMPATH_DATA_DIR` 指定其他私有数据目录。密码使用带随机盐的 scrypt 散列；会话使用 HttpOnly Cookie，HTTPS 环境下启用 Secure。保存、删除及退出操作包含同源和 CSRF 检查，计划按账号归属隔离。

数据库、环境配置、密钥、工具和私人截图不纳入 Git。仓库采用文件白名单，新增源码文件时需同步更新 `.gitignore`。应用层防护范围及部署配置见 [安全说明](docs/security-hardening.md)。

## 文件结构

| 文件 | 用途 |
| --- | --- |
| `index.html`、`demo.html`、`trial.html`、`account.html` | 四个原生网页 |
| `styles.css`、`assets/` | 共享样式与本地 SVG |
| `script.js`、`trial.js`、`account.js` | 页面交互、API 请求和结果显示 |
| `backend/` | 计划生成、时间适配、账号存储和请求防护 |
| `deployment/pythonanywhere_wsgi.py` | 可选 PythonAnywhere WSGI 适配器 |
| `tests/` | 自动化回归检查 |
| `scripts/` | 本地启动及源码包构建、核验 |

## 测试

```text
python -m pip install -r requirements-test.txt -r requirements-deploy.txt
python -m pytest tests -q -p no:cacheprovider
```

测试使用临时数据库。依赖 Unix fork 的检查会在 Windows 跳过。

详细启动和源码包说明见 [README-SUBMISSION.md](README-SUBMISSION.md)；代码及第三方组件说明见 [source-provenance.md](docs/source-provenance.md)。
