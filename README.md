# 基于经典协议的邮件客户端开发与机器学习反垃圾机制

---
## 李雨桐 - Skeleton

用户写邮件 -> MIME 构造 -> SMTP Client 发送 -> SMTP Server 接收 -> 保存 `.eml` -> SQLite 保存元数据 -> POP3 Client 拉取 -> MIME Parser 解析 -> Spam Filter 判断 -> inbox/spam 分类 -> 发件人按 `mail_id` 撤回。

## 已实现的基础功能

- SMTP 邮件发送：`smtplib` 客户端，支持纯文本、HTML、多附件和 SMTP AUTH。
- SMTP Server 模拟接收：`aiosmtpd` handler 接收入站邮件。
- POP3 邮件接收：`poplib` 客户端，接收后可保存本地 `.eml` 并提取 HTML/附件。
- 最小 POP3 Server：`socketserver` 支持 USER、PASS、STAT、LIST、RETR、DELE、QUIT。
- MIME 邮件构造和解析：支持纯文本、HTML 接口、附件接口和 `.eml` 解析。
- 用户登录认证接口：SQLite 用户表，密码用 SHA-256 hash。
- SQLite 邮件元数据存储：保存邮件、收件人、状态。
- `.eml` 文件保存：按用户和文件夹保存 inbox、spam、sent、recalled。
- 客户端演示交互：支持邮件编号读取、可撤回邮件列表、TLS 配置展示和友好错误提示。

## 已实现的扩展功能

- 智能垃圾邮件过滤：`is_spam(text)` 为主接口，优先加载 `joblib` 模型，未训练模型时使用关键词 fallback。
- 邮件撤回：发件人可按 `mail_id` 撤回自己发出的邮件，收件人副本移动到 recalled 状态。

## 安装依赖

```bash
pip install -r requirements.txt
```

## 初始化数据库

数据库会在启动服务器或 CLI 时自动初始化，也可以手动运行：

```bash
python -c "from mailapp.config import load_config; from mailapp.storage.db import init_database; load_config(); init_database()"
```

## 启动服务器

```bash
python run_server.py
```

默认 SMTP 地址为 `127.0.0.1:2525`，POP3 地址为 `127.0.0.1:1110`。按 `Ctrl+C` 退出。

## 启动客户端

```bash
python run_client.py
```

默认用户：

- `alice@example.com` / `alice123`
- `bob@example.com` / `bob123`

### 客户端菜单说明

启动 `python run_client.py` 后，命令行菜单包括：

- `1. Send Email`：发送邮件。可选择纯文本或 HTML；正文支持多行输入，以单独一行 `.` 结束；附件路径用英文逗号分隔。发送成功后会同时显示客户端 MIME ID、标准 `Message-ID` 和服务端生成的 `server mail_id`，其中 `server mail_id` 用于撤回。
- `2. Receive Email via POP3`：通过 POP3 拉取当前 inbox 邮件。接收时会保存本地 `.eml`，并提取 HTML 正文和附件到 `data/client_downloads/<user>/` 下。
- `3. List Inbox` / `4. List Spam`：列出对应文件夹邮件。列表会显示 `001`、`002` 这样的编号以及真实 `mail_id`。
- `5. Read Email`：读取邮件内容。可输入真实 `mail_id`，也可输入 inbox 编号，例如 `01`、`001` 或 `2`。读取操作只显示内容，不会重复生成 HTML/附件副本。
- `6. Recall Email`：撤回邮件。这里应输入服务端生成的 `server mail_id`。
- `7. Show TLS Settings`：显示当前 SMTP/POP3 客户端使用的安全模式，例如 `plain`、`starttls` 或 `ssl`。
- `8. List Recallable Sent Mail`：列出当前发件人可用于撤回的已发送邮件及其真实 `mail_id`。

### 本地接收文件目录

客户端通过 POP3 接收邮件后，会在 `client_download_root` 配置项指定的目录保存本地副本。默认路径为：

```text
data/client_downloads/<username>/
```

其中 `<username>` 会把邮箱地址中的 `@` 转为 `_at_`。例如 Bob 的目录为：

```text
data/client_downloads/bob_at_example.com/
```

常见子目录：

- `inbox/`：接收后保存的 `.eml` 原始邮件。
- `spam/`：客户端判定为垃圾邮件时保存的 `.eml`。
- `html/`：HTML 邮件正文另存的 `.html` 文件。
- `attachments/`：邮件附件。

## 训练垃圾邮件模型

```bash
python -m mailapp.spam.train_spam
```

没有真实数据集时会使用 toy dataset 保存 `data/models/spam_model.joblib`。真实实验建议使用 Enron-Spam Dataset 或整理好的 `text,label` CSV：

```bash
python -m mailapp.spam.train_spam --dataset data/enron_spam --model-type naive_bayes
python -m mailapp.spam.train_spam --dataset data/spam.csv --model-type svm
```

训练脚本会输出并保存 Accuracy、分类报告、混淆矩阵和 `data/models/spam_metrics.json`。如果安装了 `matplotlib`，会保存混淆矩阵图片；否则会保存文本版矩阵。

## 运行测试

```bash
python -m compileall .
pytest
```

项目根目录包含 `pytest.ini`，用于确保 pytest 能正确导入 `mailapp`，并把测试临时目录放到 `data/pytest_tmp`，避免 Windows 系统临时目录权限问题。

当前自动化测试包括 MIME、存储、spam、撤回和函数级端到端流程。真实 socket 并发测试可使用 `scripts/concurrency_test.py`。

## 项目结构说明

```text
mail_client_project/
|
|-- README.md
|-- requirements.txt
|-- config.yaml
|-- run_server.py
|-- run_client.py
|
|-- data/
|   |-- mailboxes/
|   |   `-- .gitkeep
|   `-- models/
|       `-- .gitkeep
|
|-- docs/
|   |-- design.md
|   |-- protocol.md
|   `-- test_plan.md
|
|-- mailapp/
|   |-- __init__.py
|   |-- config.py
|   |
|   |-- common/
|   |   |-- __init__.py
|   |   |-- constants.py
|   |   |-- logger.py
|   |   `-- exceptions.py
|   |
|   |-- auth/
|   |   |-- __init__.py
|   |   `-- user_store.py
|   |
|   |-- mime/
|   |   |-- __init__.py
|   |   |-- mime_builder.py
|   |   `-- mime_parser.py
|   |
|   |-- protocols/
|   |   |-- __init__.py
|   |   |-- smtp_client.py
|   |   |-- smtp_server.py
|   |   |-- pop3_client.py
|   |   |-- pop3_server.py
|   |   `-- ssl_utils.py
|   |
|   |-- storage/
|   |   |-- __init__.py
|   |   |-- db.py
|   |   |-- schema.sql
|   |   |-- mail_store.py
|   |   `-- mailbox.py
|   |
|   |-- spam/
|   |   |-- __init__.py
|   |   |-- dataset.py
|   |   |-- features.py
|   |   |-- classifier.py
|   |   `-- train_spam.py
|   |
|   |-- recall/
|   |   |-- __init__.py
|   |   `-- recall_service.py
|   |
|   |-- client/
|   |   |-- __init__.py
|   |   |-- client_core.py
|   |   `-- cli.py
|   |
|   `-- server/
|       |-- __init__.py
|       `-- server_app.py
|
`-- tests/
    |-- test_mime.py
    |-- test_storage.py
    |-- test_spam.py
    |-- test_recall.py
    `-- test_end_to_end.py
```

### 根目录文件

- `README.md`：项目说明、运行方式、结构说明和 TODO。
- `requirements.txt`：项目依赖，包括 `aiosmtpd`、`scikit-learn`、`joblib`、`pyyaml`、`pytest`。
- `config.yaml`：SMTP/POP3 地址、数据库路径、邮箱根目录、垃圾邮件模型路径、默认用户。
- `pytest.ini`：pytest 配置，指定测试目录、项目导入路径和项目内临时目录。
- `run_server.py`：服务器启动入口，调用 `mailapp.server.server_app.start_server()`。
- `run_client.py`：命令行客户端入口，调用 `mailapp.client.cli.run_cli()`。

### data

- `data/mailboxes/`：保存用户邮箱目录。运行后会按用户生成 `inbox`、`spam`、`sent`、`recalled` 子目录。
- `data/models/`：保存垃圾邮件分类模型，例如 `spam_model.joblib`。
- `.gitkeep`：保证空目录能被版本控制保留。

### docs

- `docs/design.md`：总体架构、模块划分、数据流、垃圾过滤流程和撤回流程。
- `docs/protocol.md`：SMTP、POP3、MIME、SSL/TLS 的项目内使用方式和教学简化说明。
- `docs/test_plan.md`：MIME、存储、spam、撤回、端到端测试计划和演示步骤。

### mailapp/config.py

负责读取 `config.yaml`，提供：

- `load_config(config_path="config.yaml")`
- `get_config()`

后续模块统一通过这里读取数据库、邮箱目录、服务端口和模型路径。

### mailapp/common

- `constants.py`：集中定义邮箱文件夹、邮件状态、spam/ham 标签。
- `logger.py`：统一 logging 格式，避免重复添加 handler。
- `exceptions.py`：定义项目异常，例如认证失败、邮件不存在、撤回失败、模型不存在。

### mailapp/auth

- `user_store.py`：用户管理与认证。

主要接口：

- `create_user(username, password)`
- `verify_user(username, password)`
- `get_user(username)`
- `list_users()`
- `ensure_default_users(users)`

密码用 SHA-256 做简单 hash，满足课程项目演示需要。

### mailapp/mime

- `mime_builder.py`：构造 MIME 邮件。
- `mime_parser.py`：解析 `.eml` 文件或原始 bytes。

主要能力：

- 构造纯文本邮件。
- 构造 HTML 邮件。
- 构造带附件邮件。
- 解析发件人、收件人、主题、日期、Message-ID。
- 提取正文、附件和用于 spam 检测的文本。

### mailapp/protocols

- `smtp_client.py`：使用 `smtplib` 连接 SMTP Server 并发送 MIME 邮件。
- `smtp_client.py` 支持 `plain/starttls/ssl` 三种安全模式，支持 HTML、附件和发送回执。
- `smtp_server.py`：使用 `aiosmtpd` 接收入站邮件，并调用存储层保存。
- `pop3_client.py`：使用 `poplib` 拉取、列出、删除邮件。
- `pop3_client.py` 支持 `plain/starttls/ssl` 三种安全模式。
- `pop3_server.py`：使用 `socketserver` 实现最小 POP3 Server。
- `ssl_utils.py`：SSL/TLS context 和 socket 包装工具函数。

当前 POP3 Server 支持：

- `USER`
- `PASS`
- `STAT`
- `LIST`
- `RETR`
- `DELE`
- `QUIT`

### mailapp/storage

- `schema.sql`：SQLite 建表脚本。
- `db.py`：数据库连接、初始化和通用查询函数。
- `mailbox.py`：用户邮箱目录和 `.eml` 文件管理。
- `mail_store.py`：邮件整体存储逻辑。

核心数据表：

- `users`：用户账号和密码 hash。
- `emails`：邮件元数据，包括 `mail_id`、`message_id`、发件人、主题、状态、是否 spam。
- `recipients`：收件人视角的邮件状态，包括文件夹、已读状态、删除标记。
- `mail_status`：撤回等状态变更记录。

### mailapp/spam

- `dataset.py`：加载垃圾邮件数据集；没有真实数据时返回 toy dataset。
- `features.py`：TF-IDF 特征提取。
- `classifier.py`：垃圾邮件分类主接口。
- `train_spam.py`：模型训练脚本。

主流程只调用：

```python
is_spam(text)
```

如果 `data/models/spam_model.joblib` 存在，会优先加载模型预测；否则使用关键词 fallback。后续组员可以在不改主流程的情况下替换为 TF-IDF + Naive Bayes 或 SVM。

### mailapp/recall

- `recall_service.py`：邮件撤回功能。

主要接口：

- `request_recall(sender, mail_id)`
- `can_recall(sender, mail_id)`
- `recall_email(sender, mail_id)`
- `notify_recipients_recalled(mail_id)`
- `get_recall_status(mail_id)`

撤回规则：

- 邮件必须存在。
- 只有原始发件人可以撤回。
- 已撤回邮件不能重复撤回。
- 撤回后邮件状态为 `recalled`，收件人 inbox 不再正常显示原邮件。

### mailapp/client

- `client_core.py`：客户端核心流程，负责组合 MIME、SMTP、POP3、spam、recall 等模块。
- `cli.py`：命令行交互界面。

CLI 菜单包括：

- Send Email
- Receive Email via POP3
- List Inbox
- List Spam
- Read Email
- Recall Email
- Show TLS Settings
- List Recallable Sent Mail
- Exit

### mailapp/server

- `server_app.py`：统一启动服务端。

启动时会完成：

- 读取配置。
- 初始化 SQLite 数据库。
- 创建默认用户。
- 启动 SMTP Server。
- 启动 POP3 Server。

### tests

- `test_mime.py`：测试 MIME 构造与解析。
- `test_storage.py`：测试邮件入库和用户邮件列表。
- `test_spam.py`：测试关键词 spam/ham 判断。
- `test_recall.py`：测试发件人撤回和非发件人撤回失败。
- `test_end_to_end.py`：函数级最小端到端测试。

当前端到端测试以函数级集成为主，真实 socket 级 SMTP/POP3 测试留给后续完善。

## SSL/TLS 说明

客户端侧 `smtp_client.py` 与 `pop3_client.py` 支持以下安全模式：

- `plain`：普通明文连接，当前 `config.yaml` 默认配置。
- `starttls`：先建立普通连接，再升级为 TLS。
- `ssl`：隐式 SSL/TLS 连接。

相关可选配置示例：

```yaml
smtp_security: "plain"     # plain / starttls / ssl
pop3_security: "plain"     # plain / starttls / ssl
ssl_verify: true
ssl_cafile: "path/to/ca.pem"
```

兼容旧配置：如果未配置 `smtp_security` / `pop3_security`，客户端会继续读取 `use_ssl`、`smtp_use_ssl`、`pop3_use_ssl`、`smtp_starttls`、`pop3_starttls` 等字段。

注意：当前服务端仍需进一步配置证书和 TLS 监听后，才能完成真正端到端的 SSL/TLS 演示。

## SMTP AUTH 说明

SMTP Server 通过 `aiosmtpd` 的 `authenticator` 钩子接入 `mailapp.auth.user_store.verify_user`，支持 `AUTH PLAIN` 与 `AUTH LOGIN`。相关配置：

- `smtp_auth_required`（默认 `true`）：强制客户端在 `MAIL FROM` 之前完成 AUTH。
- `smtp_auth_require_tls`（默认 `false`）：是否要求先 `STARTTLS` 再 AUTH，演示环境默认关闭。

`SMTPHandler.handle_DATA` 会校验已认证用户与 `MAIL FROM` 一致，避免简单的发件人伪造。

## TODO

- 为 POP3 Server 补齐更完整的 RFC 1939 行结束、状态机和并发压力测试。
- 用真实垃圾邮件数据集训练 TF-IDF + Naive Bayes 或 SVM。
- 服务端侧补齐 SSL/TLS 证书配置与 STARTTLS/SSL 监听，配合客户端完成加密传输演示。
- 增加真实 socket 级端到端测试和并发测试。
