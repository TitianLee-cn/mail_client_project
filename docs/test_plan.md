# 测试计划

## MIME 测试

验证纯文本邮件构造、Message-ID、X-MailApp-Mail-ID、正文解析。

## 存储测试

验证入站邮件生成 `mail_id`，写入 emails/recipients 表，并按 spam 判断保存到 inbox 或 spam。

## 垃圾邮件过滤测试

验证关键词 `lottery`、`winner`、`free`、`prize`、`click`、`money`、`urgent`、`win` 可以触发 spam，普通课程文本为 ham。

验证训练脚本可以从 `text,label` CSV 或 ham/spam 目录读取样本，训练 TF-IDF + Naive Bayes/SVM 模型，保存 `spam_model.joblib`，并输出 Accuracy、分类报告、混淆矩阵和 JSON 指标文件。

验证 `is_spam(text)` 在模型文件存在时优先使用模型预测，在模型不存在或加载失败时回退到关键词 fallback。

## 邮件撤回测试

验证原发件人可以撤回自己的邮件，其他用户不能撤回。撤回后状态为 recalled，收件人 inbox 不再显示原邮件。

## 端到端测试

当前采用函数级最小集成测试：MIME 构造、SMTP Server 的消息处理函数、存储、垃圾过滤、撤回串起来验证。TODO 是增加真实 SMTP/POP3 socket 启动后的测试。

## 演示步骤

1. `python run_server.py`
2. `python run_client.py`
3. Alice 给 Bob 发送普通邮件。
4. Bob 接收并查看 inbox。
5. Alice 发送包含 `Win Lottery Now` 的邮件。
6. Bob 查看 spam 文件夹。
7. Alice 根据普通邮件 `mail_id` 撤回。
8. Bob 的 inbox 不再显示该邮件。
