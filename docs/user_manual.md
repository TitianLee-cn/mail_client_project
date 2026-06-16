# 用户手册

## 1. 环境准备

进入项目目录：

```bash
cd mail_client_project_renewed
```

建议使用 Conda 环境：

```bash
conda activate agent_2
```

安装依赖：

```bash
pip install -r requirements.txt
```

如果证书不存在，生成本地开发证书：

```bash
bash scripts/generate_dev_cert.sh
```

## 2. 一键启动

推荐运行：

```bash
chmod +x run.sh
./run.sh
```

等价命令：

```bash
python run_demo.py
```

启动成功后终端显示：

```text
Demo services started: SMTP 127.0.0.1:2525, POP3 127.0.0.1:1110
```

`run_demo.py` 会同时启动：

- SMTP 服务：`127.0.0.1:2525`
- POP3 服务：`127.0.0.1:1110`
- Tkinter 桌面 GUI

## 3. 默认账户

系统默认创建两个账户：

```text
alice@example.com / alice123
bob@example.com   / bob123
```

也可以在 GUI 中点击 `Register` 注册新账户。

## 4. 配置说明

配置文件：`config.yaml`

关键字段：

```yaml
smtp_host: "127.0.0.1"
smtp_port: 2525
smtp_security: "starttls"
smtp_auth_required: true

pop3_host: "127.0.0.1"
pop3_port: 1110
pop3_security: "starttls"

tls_certfile: "certs/mailapp-cert.pem"
tls_keyfile: "certs/mailapp-key.pem"
ssl_cafile: "certs/mailapp-cert.pem"
ssl_verify: true

database_path: "data/email.db"
mailbox_root: "data/mailboxes"
client_download_root: "data/client_downloads"
spam_model_path: "data/models/spam_model.joblib"
```

如果要换服务器 IP 或端口，修改 `smtp_host`、`smtp_port`、`pop3_host`、`pop3_port` 后重新启动程序。

## 5. GUI 功能

### 5.1 登录

1. 输入用户名和密码。
2. 点击 `Login`。
3. 登录后可以访问 Compose、Inbox、Spam、Sent / Recall 等页签。

### 5.2 发送邮件

1. 打开 `Compose`。
2. 填写 Recipients、Subject、Body。
3. 可点击 `Add Attachments` 添加附件。
4. 可勾选 `Send as HTML` 发送 HTML 邮件。
5. 点击 `Send Email`。

发送成功后，GUI 会弹出 Message-ID 和 Server mail_id。

### 5.3 接收邮件

1. Bob 登录。
2. 打开 `Inbox`。
3. 点击 `Receive via POP3`。
4. 系统通过 POP3 STLS 下载邮件。
5. 普通邮件保留在 Inbox。
6. 垃圾邮件会移动到 Spam。

本地保存目录：

```text
data/client_downloads/<user>/
```

例如 Bob 的附件和 `.eml` 文件位于：

```text
data/client_downloads/bob_at_example.com/
```

### 5.4 查看邮件

在 Inbox 或 Spam 中双击邮件，或选中后点击 `Open Selected`。

窗口会显示：

- Status
- From
- To
- Subject
- Date
- Server mail_id
- Body type
- Body

### 5.5 垃圾邮件显示

点击 `Fill Spam Demo` 可自动填入典型垃圾邮件内容。

Bob 接收后：

- 邮件进入 Spam 页签。
- 主题前加 `[SPAM]`。
- 行显示为红色高亮。

### 5.6 邮件撤回

1. Alice 登录。
2. 打开 `Sent / Recall`。
3. 点击 `Refresh Sent`。
4. 选中要撤回的邮件。
5. 点击 `Recall Selected`。
6. Bob 的 inbox 不再显示该邮件。
7. Bob 可在 `Recall Notifications` 查看通知。

### 5.7 TLS 与模型状态

打开 `TLS & Model` 可查看：

- SMTP 地址、端口、安全模式。
- POP3 地址、端口、安全模式。
- 是否校验证书。
- CA 文件路径。
- Spam 模型是否可用。
- 模型类型和训练样本数。

## 6. 中间人攻击演示

生成攻击者证书：

```bash
openssl req -x509 -newkey rsa:3072 -sha256 -nodes \
  -keyout certs/attacker-key.pem \
  -out certs/attacker-cert.pem \
  -days 3650 \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
```

备份正常配置：

```bash
cp config.yaml config.good.yaml
```

切换到攻击者 CA：

```bash
python -c 'from pathlib import Path; p=Path("config.yaml"); s=p.read_text(); s=s.replace("ssl_cafile: \"certs/mailapp-cert.pem\"", "ssl_cafile: \"certs/attacker-cert.pem\""); p.write_text(s)'
```

重新启动：

```bash
python run_demo.py
```

尝试发送邮件，应看到 certificate verify failed / TLS handshake failed。

恢复正常配置：

```bash
cp config.good.yaml config.yaml
python run_demo.py
```

## 7. 测试命令

编译检查：

```bash
python -m compileall -q mailapp tests scripts run_server.py run_client.py run_gui.py run_demo.py
```

自动化测试：

```bash
python -m pytest -q
```

并发压力测试：

```bash
python run_server.py
python scripts/concurrency_test.py --clients 50
```

生成垃圾邮件混淆矩阵图片：

```bash
MPLCONFIGDIR=/tmp python scripts/plot_spam_confusion_matrix.py
```

## 8. 常见问题

### 8.1 `No module named yaml`

说明当前 Python 环境不对。请先激活环境或安装依赖：

```bash
conda activate agent_2
pip install -r requirements.txt
```

### 8.2 `TLS certificate/key missing`

运行：

```bash
bash scripts/generate_dev_cert.sh
```

### 8.3 `Connection refused`

说明服务端没有启动。请先运行：

```bash
python run_demo.py
```

或单独启动服务端：

```bash
python run_server.py
```

### 8.4 完整 pytest 中 socket 权限失败

如果在受限沙箱中运行，协议测试可能无法创建本地 socket。请在正常终端中运行 pytest。
