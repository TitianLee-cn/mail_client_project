# 邮件客户端系统设计文档

## 1. 项目目标

本项目实现一个可本地演示的邮件客户端与模拟邮件服务器系统，覆盖 SMTP 发送、POP3 接收、MIME 编解码、TLS 加密、SQLite 持久化、附件保存、垃圾邮件分类和邮件撤回。系统同时提供桌面 GUI、CLI 入口和自动化测试，便于课堂演示和实验验收。

## 2. 总体架构

核心链路如下：

```text
GUI/CLI Client
  -> MIME Builder
  -> SMTP STARTTLS + AUTH
  -> SMTP Server
  -> SQLite Metadata + .eml Mailbox
  -> POP3 STLS
  -> Client Receive + MIME Parser + Spam Classifier
```

主要目录：

- `mailapp/client/`：GUI、CLI 和客户端工作流。
- `mailapp/protocols/`：SMTP/POP3 客户端、服务端和 TLS 工具。
- `mailapp/mime/`：纯文本、HTML、附件 MIME 构造和解析。
- `mailapp/storage/`：SQLite 元数据、用户邮箱目录、`.eml` 文件操作。
- `mailapp/auth/`：用户注册、登录校验和默认账户初始化。
- `mailapp/spam/`：数据集加载、TF-IDF 特征、模型训练、预测和指标保存。
- `mailapp/recall/`：邮件撤回、状态更新和通知记录。
- `tests/`：pytest 自动化测试。
- `scripts/`：证书生成、语料下载、并发压力测试、混淆矩阵绘图。

## 3. 协议交互流程

### 3.1 SMTP 发送

1. 用户在 GUI 中填写收件人、主题、正文和附件。
2. 客户端用 MIME 构造邮件，生成 `Message-ID` 和 `X-MailApp-Mail-ID`。
3. 客户端连接 SMTP 服务器 `127.0.0.1:2525`。
4. 服务端要求 `STARTTLS`，客户端完成 TLS 握手并校验证书。
5. 客户端执行 SMTP AUTH，用户名必须与发件人一致。
6. 客户端发送 `MAIL FROM`、`RCPT TO`、`DATA`。
7. 服务端生成服务端唯一 `mail_id`，保存收件人 inbox 副本和发件人 sent 副本。

### 3.2 POP3 接收

1. Bob 登录 GUI 后点击 `Receive via POP3`。
2. 客户端连接 POP3 服务器 `127.0.0.1:1110`。
3. 服务端要求 `STLS` 后才能 `USER/PASS`。
4. 客户端通过 `UIDL` 获取服务端 `mail_id`，通过 `RETR` 下载 MIME 原文。
5. 客户端解析 header、正文、HTML 和附件。
6. 客户端调用垃圾邮件分类器。
7. 普通邮件保留在 inbox；垃圾邮件移动到 Spam 文件夹并在 GUI 中显示 `[SPAM]` 和红色高亮。
8. `.eml` 与附件保存到 `data/client_downloads/<user>/`。

## 4. MIME 设计

系统支持：

- `text/plain` 邮件。
- `text/html` 邮件，并自动生成 plain fallback。
- 多附件发送和接收。
- 解析 `From`、`To`、`Subject`、`Date`、`Message-ID`。
- 接收端保存原始 `.eml` 文件。
- 接收端提取附件到本地目录。

附件通过 Python `email` 标准库添加为 MIME part，解析时使用安全文件名写入本地目录，避免直接信任远端路径。

## 5. 存储设计

系统同时使用 SQLite 和文件系统：

- SQLite 保存用户、邮件元数据、收件人关系、状态、通知等。
- 文件系统保存每个用户的 `.eml` 副本。
- inbox、spam、sent、recalled 分别对应不同目录。

SQLite 配置：

- 启用 WAL，提升并发写入稳定性。
- 启用 foreign key。
- 设置 busy timeout，降低并发发送时的锁冲突。

## 6. TLS 与中间人防护

配置文件 `config.yaml` 默认启用：

- SMTP：`starttls`
- POP3：`starttls`
- `ssl_verify: true`
- CA 文件：`certs/mailapp-cert.pem`

服务端证书由 `scripts/generate_dev_cert.sh` 生成。客户端用配置中的 CA 校验证书。演示中如果把 `ssl_cafile` 改成攻击者证书，客户端会拒绝 TLS 握手并提示 certificate verify failed，从而展示中间人伪造证书无法通过验证。

## 7. 垃圾邮件分类设计

模型训练流程：

1. `scripts/download_spamassassin_corpus.py` 下载 Apache SpamAssassin Public Corpus。
2. `mailapp/spam/features.py` 使用 TF-IDF 向量化文本。
3. `mailapp/spam/train_spam.py` 支持 Multinomial Naive Bayes 和 Linear SVM。
4. 当前提交模型使用 Linear SVM。
5. 模型保存为 `data/models/spam_model.joblib`。
6. 指标保存为 `data/models/spam_metrics.json`。

当前模型结果：

- 数据集：Apache SpamAssassin Public Corpus。
- 总样本：3002。
- 训练样本：2401。
- 测试样本：601。
- Accuracy：98.67%。
- Spam recall：92%。
- Confusion matrix：`[[501, 0], [8, 92]]`。

运行时如果模型文件缺失，系统会退回关键词规则检测，保证 demo 仍可运行。

## 8. 邮件撤回设计

邮件撤回基于服务端唯一 `mail_id`：

1. 发件人重新认证。
2. 服务端检查邮件存在、未撤回、且请求者是发件人。
3. SQLite 事务中更新邮件状态为 `recalled`。
4. 收件人副本从 inbox/spam 移入 recalled。
5. 收件人 inbox 不再显示该邮件。
6. 收件人可在 Recall Notifications 查看撤回通知。

该功能只适用于本项目模拟服务器内部的邮件。

## 9. GUI 设计

GUI 使用 Tkinter，主要页签：

- `Compose`：发送纯文本/HTML 邮件和附件。
- `Inbox`：POP3 接收、刷新、打开邮件。
- `Spam`：显示被分类为垃圾邮件的邮件，主题加 `[SPAM]` 并变色。
- `Sent / Recall`：查看可撤回邮件并执行撤回。
- `Recall Notifications`：查看撤回通知。
- `TLS & Model`：显示 SMTP/POP3 TLS 配置和垃圾邮件模型状态。

## 10. 并发设计

- SMTP 服务端基于 `aiosmtpd`。
- POP3 服务端基于 `ThreadingTCPServer`。
- 数据库启用 WAL 和 timeout。
- 自动化测试覆盖 10 客户端并发发送。
- 手动压力测试脚本支持 50 客户端并发，并输出成功率、吞吐量和延迟统计。

## 11. 运行入口

推荐运行：

```bash
cd mail_client_project_renewed
conda activate agent_2
./run.sh
```

等价方式：

```bash
python run_demo.py
```

`run_demo.py` 会同时启动 SMTP/POP3 服务和桌面 GUI。
