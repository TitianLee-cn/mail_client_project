# 设计说明

## 总体架构

项目分为客户端、协议层、服务端、存储层、垃圾过滤和撤回服务。客户端负责构造 MIME 邮件并调用 SMTP 发送；服务端接收邮件后写入 `.eml` 文件和 SQLite；POP3 服务从 SQLite 查询可见邮件并返回原始 `.eml`；客户端拉取后解析 MIME 并展示摘要。

## 模块划分

- `mime`：封装 `EmailMessage` 构造和 `BytesParser` 解析。
- `protocols`：封装 SMTP/POP3 socket 交互，保留 SSL/TLS 工具。
- `storage`：管理 `users`、`emails`、`recipients`、`mail_status` 表和用户邮箱目录。
- `spam`：提供 `is_spam(text)`，后续可替换为机器学习模型。
- `recall`：按 `mail_id` 实现服务器内部撤回。
- `client` / `server`：组合各模块形成可演示流程。

## 数据流

1. 用户输入发件人、收件人、主题、正文。
2. MIME builder 构造 `EmailMessage`。
3. SMTP client 发送给本地 SMTP server。
4. SMTP server 调用 `store_incoming_email`。
5. 存储层生成 `mail_id`，保存 `.eml` 和 SQLite 元数据。
6. POP3 client 通过 POP3 server 拉取 inbox 中正常邮件。
7. MIME parser 解析邮件正文和附件。

## 垃圾邮件过滤流程

`store_incoming_email` 会提取主题与正文，调用 `spam.classifier.is_spam(text)`。如果模型文件存在，使用 TF-IDF + 分类器预测；如果不存在，使用关键词 fallback。判定为 spam 的邮件进入 `spam` 文件夹，否则进入 `inbox`。

## 邮件撤回流程

发件人调用 `request_recall(sender, mail_id)`。服务会检查邮件存在、发件人匹配且未撤回，然后把 `emails.status` 改为 `recalled`，把收件人记录移动到 `recalled` 文件夹，并尽量移动对应 `.eml` 文件。收件人读取时显示“该邮件已被撤回”。
