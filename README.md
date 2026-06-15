# 基于经典协议的邮件客户端与机器学习反垃圾系统

课程项目实现 SMTP、POP3、MIME、TLS、SQLite、本地 `.eml`、机器学习垃圾过滤和服务端邮件撤回。

## 任务完成情况

| 要求 | 实现 |
|---|---|
| SMTP 纯文本/HTML/附件 | `smtplib` + `EmailMessage` |
| POP3 列表与下载 | RFC 1939 状态机、LIST/RETR/UIDL |
| 用户认证 | SMTP AUTH PLAIN/LOGIN、POP3 USER/PASS |
| SSL/TLS | SMTP STARTTLS、POP3 STLS，TLS 1.2+ |
| 本地存储 | 原始 `.eml`、HTML 正文和附件 |
| 模拟服务器 | `aiosmtpd` SMTP + 多线程 POP3 |
| 并发 | 自动化 10 客户端测试及独立压力脚本 |
| SQLite 元数据 | 发件人、收件人、时间、状态、文件夹 |
| 智能垃圾过滤 | SpamAssassin 公开语料、TF-IDF + SVM |
| 邮件撤回 | 认证后按服务端唯一 mail_id 事务撤回 |

## 用户手册

### 1. 安装与启动

进入项目目录并安装依赖：

```bash
cd /mnt/e/AI4Titi/0.5_ComputerNetwork/final_project/mail_client_project_renewed
pip install -r requirements.txt
scripts/generate_dev_cert.sh
```

证书和私钥只在本机生成，不上传 GitHub。Windows 原生命令行无法直接执行 `.sh` 时，可在 Git Bash/WSL 中运行该脚本，或使用项目所处的 Linux 环境生成。

#### GUI 一键启动（课堂推荐）

```bash
python run_demo.py
```

该命令会同时启动 SMTP 服务、POP3 服务和 Tkinter 桌面客户端。关闭 GUI 后服务会自动停止。

#### GUI 与服务端分别启动

终端 1：

```bash
python run_server.py
```

终端 2：

```bash
python run_gui.py
```

#### 命令行客户端启动

先在终端 1运行 `python run_server.py`，再在终端 2运行：

```bash
python run_client.py
```

默认账号：

- `alice@example.com / alice123`
- `bob@example.com / bob123`

默认协议地址：

- SMTP STARTTLS：`127.0.0.1:2525`
- POP3 STLS：`127.0.0.1:1110`

### 2. 注册账号

#### GUI 操作

1. 启动 `python run_demo.py`。
2. 点击登录区的 `Register`。
3. 输入邮箱格式的用户名，例如 `carol@example.com`。
4. 输入至少 6 位密码并再次确认。
5. 点击 `Create Account`。
6. 注册成功后账号密码会自动填回登录框，点击 `Login`。

`alice@example.com` 和 `bob@example.com` 已存在，不能重复注册。

#### 终端操作

CLI 菜单没有注册项，可使用管理命令注册：

```bash
python -c "from mailapp.config import load_config; from mailapp.storage.db import init_database; from mailapp.auth.user_store import register_user; load_config(); init_database(); register_user('carol@example.com', 'carol123')"
```

注册后使用 `python run_client.py` 登录。用户名必须是邮箱格式，密码至少 6 位。

### 3. 登录与切换用户

#### GUI 操作

1. 在顶部输入用户名和密码。
2. 点击 `Login`。
3. 登录后可访问 Compose、Inbox、Spam 等页签。
4. 切换用户时点击 `Logout`，再输入另一账号登录。

#### 终端操作

CLI 没有持续登录会话，每次执行发送、接收、读取、撤回等操作时都会要求输入用户名和密码。

### 4. 发送纯文本邮件

#### GUI 操作

1. 登录发件人账号。
2. 打开 `Compose`。
3. 在 Recipients 输入项目内已注册的收件人，可用逗号或分号分隔多人。
4. 输入 Subject 和 Body。
5. 不勾选 `Send as HTML`。
6. 点击 `Send Email`。
7. 成功弹窗会显示标准 Message-ID 和用于撤回的 Server mail_id。

`Fill Normal Demo` 可以自动填入课堂演示用普通邮件。

#### 终端操作

1. 运行 `python run_client.py`。
2. 选择 `1. Send Email`。
3. 输入发件人用户名和密码。
4. 输入收件人，多个地址使用英文逗号分隔。
5. 输入主题。
6. `Send as HTML` 选择 `n`。
7. 输入多行正文，以单独一行 `.` 结束。
8. 附件留空后回车。

### 5. 发送 HTML 邮件

#### GUI 操作

1. 在 `Compose` 填写收件人和主题。
2. 正文中输入 HTML，例如 `<h1>Hello</h1><p>Network project</p>`。
3. 勾选 `Send as HTML`。
4. 点击 `Send Email`。

系统会构造 `multipart/alternative`，同时保留纯文本回退正文。

#### 终端操作

选择 `1. Send Email`，在 `Send as HTML` 提示处输入 `y`，再输入 HTML 正文并以 `.` 结束。

### 6. 发送带附件邮件

#### GUI 操作

1. 在 `Compose` 点击 `Add Attachments`。
2. 在文件选择窗口中选择一个或多个图片、文档等文件。
3. 页面会显示附件数量和文件名。
4. 填写邮件后点击 `Send Email`。
5. 需要取消附件时点击 `Clear Attachments`。

#### 终端操作

选择 `1. Send Email`。输入正文后，在 `Attachment paths comma-separated` 提示处输入完整文件路径；多个附件用英文逗号分隔，例如：

```text
/home/user/report.pdf,/home/user/image.png
```

### 7. 通过 POP3 接收邮件

#### GUI 操作

1. 使用收件人账号登录。
2. 打开 `Inbox`。
3. 点击 `Receive via POP3`。
4. 客户端通过 POP3 STLS 下载当前 inbox 邮件。
5. 弹窗会显示接收数量和识别出的垃圾邮件数量。
6. 点击 `Refresh` 更新当前列表。

#### 终端操作

1. 选择 `2. Receive Email via POP3`。
2. 输入收件人用户名和密码。
3. 程序显示每封邮件的编号、HAM/SPAM、正文类型、附件和保存路径。

### 8. 将邮件保存为 `.eml`

GUI 和 CLI 都会在执行 POP3 接收时自动保存，不需要额外点击。

正常邮件：

```text
data/client_downloads/<user>/inbox/<server_mail_id>.eml
```

垃圾邮件：

```text
data/client_downloads/<user>/spam/<server_mail_id>.eml
```

邮箱地址中的 `@` 会转换成 `_at_`。例如 Bob 的目录：

```text
data/client_downloads/bob_at_example.com/inbox/
```

HTML 正文和附件分别保存在：

```text
data/client_downloads/<user>/html/
data/client_downloads/<user>/attachments/<server_mail_id>/
```

### 9. 查看收件箱、垃圾箱和邮件正文

#### GUI 操作

1. 登录后打开 `Inbox` 或 `Spam`。
2. 点击 `Refresh`。
3. 选中邮件后点击 `Open Selected`，也可以双击邮件。
4. 详情窗口显示发件人、收件人、主题、日期、mail_id、正文类型和正文。

#### 终端操作

- 选择 `3. List Inbox` 查看收件箱。
- 选择 `4. List Spam` 查看垃圾箱。
- 选择 `5. Read Email` 阅读邮件。
- 阅读时可以输入完整 server mail_id，也可以输入收件箱中的序号，例如 `1` 或 `001`。

### 10. 展示智能垃圾邮件过滤

#### GUI 操作

1. Alice 登录并打开 `Compose`。
2. 点击 `Fill Spam Demo`。
3. 点击 `Send Email`。
4. Alice 注销，Bob 登录。
5. Bob 打开 `Inbox`，点击 `Receive via POP3`。
6. 弹窗显示检测到 1 封垃圾邮件。
7. 打开 `Spam` 并点击 `Refresh`。
8. `Win Lottery Now` 邮件会出现在 Spam，不会继续留在 Inbox。

#### 终端操作

1. Alice 使用菜单 `1` 发送主题 `Win Lottery Now`。
2. 正文输入 `Claim your free cash prize and lottery money now`。
3. Bob 使用菜单 `2` 接收，输出会显示 `[SPAM]`。
4. Bob 使用菜单 `4` 查看垃圾箱。
5. 使用菜单 `10. Show Spam Model Status` 展示 SVM 模型状态。

### 11. 撤回已发送邮件

#### GUI 操作

1. 发件人登录。
2. 打开 `Sent / Recall`。
3. 点击 `Refresh Sent`。
4. 选中需要撤回的邮件。
5. 点击 `Recall Selected` 并确认。
6. 收件人登录后，该邮件不再出现在 Inbox。
7. 收件人打开 `Recall Notifications`，点击 `Refresh Notifications` 查看撤回通知。

只有原发件人能够撤回，且一封邮件不能重复撤回。

#### 终端操作

1. 发件人选择 `8. List Recallable Sent Mail`。
2. 输入发件人用户名和密码。
3. 复制目标邮件的 server mail_id。
4. 选择 `6. Recall Email`。
5. 再次输入发件人账号、密码和 server mail_id。
6. 收件人选择 `9. List Recall Notifications` 查看通知。

### 12. 查看 TLS 与模型状态

#### GUI 操作

打开 `TLS & Model` 页签，可查看：

- SMTP 地址、STARTTLS 模式和证书验证状态。
- POP3 地址、STLS 模式和证书验证状态。
- SVM 模型是否可用、训练样本数和模型文件路径。

点击 `Refresh Status` 可刷新。

#### 终端操作

- 菜单 `7. Show TLS Settings` 查看 SMTP/POP3 安全模式。
- 菜单 `10. Show Spam Model Status` 查看模型信息。

需要重新生成本地课程演示证书时，在项目根目录执行：

```bash
scripts/generate_dev_cert.sh
```

生成后重启 `run_server.py` 或 `run_demo.py`。

### 13. 退出程序

#### GUI 操作

直接关闭窗口。使用 `run_demo.py` 启动时，SMTP 和 POP3 服务会一并停止。

#### 终端操作

- CLI 菜单选择 `0. Exit`。
- 独立服务端使用 `Ctrl+C` 停止。

### 14. 使用限制

- 该系统是本地模拟邮件服务器，只能向项目内注册用户投递。
- 输入真实 Gmail、QQ 邮箱等地址不会将邮件发送到互联网。
- 邮件撤回只对本项目服务器内的副本生效。
- 项目证书只用于课程本地演示，不应用于生产环境。

## 垃圾邮件训练

当前模型结果：

- 3002 封公开语料邮件
- Accuracy：98.67%
- Spam recall：92%
- 混淆矩阵：`[[501, 0], [8, 92]]`

模型位于 `data/models/spam_model.joblib`，指标位于 `data/models/spam_metrics.json`。若模型不存在，程序保留关键词降级模式，但提交版本已包含训练模型。

### GUI 操作

GUI 不提供重新训练按钮。课堂演示直接使用项目内已有模型，并在 `TLS & Model` 页面展示模型类型、样本数量和模型路径。

### 终端操作

下载 Apache SpamAssassin 公开语料：

```bash
python scripts/download_spamassassin_corpus.py
```

训练 SVM 并生成准确率、分类报告和混淆矩阵：

```bash
python -m mailapp.spam.train_spam \
  --dataset data/datasets/spamassassin \
  --model svm \
  --test-size 0.2
```

也支持 `--model naive_bayes`，以及包含 `text,label` 两列的 CSV 或 ham/spam 目录树。

## 测试

```bash
python -m compileall -q mailapp tests scripts run_server.py run_client.py run_gui.py run_demo.py
python -m pytest -q
```

当前自动化结果：`23 passed`。真实 50 客户端 TLS/AUTH 并发实测为 50/50 成功。

执行作业要求中的 50 客户端压力测试：

```bash
python run_server.py
```

另一个终端执行：

```bash
python scripts/concurrency_test.py --clients 50
```

## 协议说明

- SMTP：RFC 5321，认证使用 AUTH PLAIN/LOGIN。
- POP3：RFC 1939，包含三状态、延迟删除、RSET、稳定编号、CRLF 和 dot-stuffing。
- MIME：RFC 2045，支持 multipart/alternative 和附件传输编码。

详细说明见：

- `docs/protocol.md`
- `docs/design.md`
- `docs/test_plan.md`

## 说明

撤回功能只对本项目服务器控制的邮箱有效。真实互联网邮件一旦投递到外部服务器，发送方无法依靠 SMTP/POP3 强制撤回。
