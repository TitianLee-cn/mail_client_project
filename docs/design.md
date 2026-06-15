# 系统设计

## 架构

`CLI -> MIME -> SMTP/TLS -> SMTP Server -> SQLite + .eml -> POP3/TLS -> Client`

主要模块：

- `protocols`：SMTP/POP3 客户端、服务端和 TLS context。
- `mime`：纯文本、HTML、附件编码与解析。
- `storage`：SQLite 元数据、用户邮箱目录及 `.eml`。
- `spam`：公开语料加载、TF-IDF、Naive Bayes/SVM、评估和模型持久化。
- `recall`：认证、所有权检查、事务状态更新、文件移动和通知记录。

## 入站与接收流程

1. 客户端建立 SMTP STARTTLS，执行 AUTH。
2. MIME 邮件经 SMTP DATA 发送。
3. 服务端生成唯一 `mail_id`，保存发件人 sent 副本、收件人 inbox 副本及 SQLite 元数据。
4. POP3 客户端建立 STLS，执行 USER/PASS。
5. 客户端通过 UIDL 获取服务端 `mail_id`，RETR 下载原始 MIME。
6. 客户端提取主题和正文，实时调用已训练模型。
7. spam 邮件的服务端副本与本地 `.eml` 保存到 spam；ham 保留在 inbox。
8. HTML 正文及附件保存到客户端用户目录。

## 垃圾邮件模型

`download_spamassassin_corpus.py` 下载 Apache SpamAssassin 公开语料。训练流程使用 TF-IDF，可选择 Multinomial Naive Bayes 或 Linear SVM。模型、向量器、训练元数据保存在一个 joblib bundle 中，测试准确率、分类报告和混淆矩阵保存为 JSON。

当前提交模型使用 Linear SVM：

- 总样本：3002
- 训练样本：2401
- 测试样本：601
- Accuracy：98.67%
- Spam recall：92%
- Confusion matrix：`[[501, 0], [8, 92]]`

## 撤回事务

1. 发件人必须再次通过用户名和密码认证。
2. 服务端按 `mail_id` 检查邮件存在、所有权和当前状态。
3. 一个 SQLite 事务内更新邮件状态、收件人文件夹、状态历史和通知记录。
4. 收件人 `.eml` 移入 recalled；事务失败时反向移动文件。
5. recalled 邮件不再出现在 POP3 inbox，收件人可查看持久化通知。

## 并发

SMTP 使用异步 `aiosmtpd`，POP3 使用 `ThreadingTCPServer`。SQLite 启用 WAL、外键和 10 秒 busy timeout。自动化测试覆盖 10 个并发 TLS/AUTH SMTP 客户端。
