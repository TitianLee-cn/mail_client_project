# 测试计划与结果

## 自动化测试

执行：

```bash
python -m compileall -q mailapp tests scripts run_server.py run_client.py run_gui.py run_demo.py
python -m pytest -q
```

当前共 23 项测试，覆盖：

- MIME 纯文本、HTML 文本回退、附件往返。
- SQLite 元数据与 `.eml` 文件保存。
- TF-IDF 模型训练、评估、保存、加载和预测。
- 发件人撤回、非发件人拒绝、错误密码拒绝。
- POP3 未认证拒绝、稳定会话、dot-stuffing、RSET、异常断开和 QUIT 删除提交。
- POP3 STLS 登录。
- SMTP STARTTLS、AUTH 和 10 客户端并发入库。
- GUI 收件人解析和错误信息转换。
- 新账号注册、登录、邮箱格式、密码长度和重复账号校验。

结果：`23 passed`。

## 公开语料模型结果

数据：Apache SpamAssassin Public Corpus，easy_ham + spam，共 3002 封。

- 模型：TF-IDF + Linear SVM
- Accuracy：98.67%
- Ham：501 正确，0 误判
- Spam：92 正确，8 漏判
- 混淆矩阵：`[[501, 0], [8, 92]]`

完整指标见 `data/models/spam_metrics.json`。

## 并发实测

```bash
python scripts/concurrency_test.py --clients 50
```

50 客户端实测结果：

- 成功发送：50/50
- SQLite 邮件记录：50/50
- SQLite 收件人记录：50/50
- 失败：0
- 总耗时：2.669 秒
- 吞吐：18.74 emails/s

## 演示顺序

1. 执行 `python run_demo.py` 同时启动服务端和桌面 GUI。
2. Alice 使用 Compose 的普通邮件模板，添加附件并发送。
3. Bob 在 Inbox 通过 POP3 STLS 接收并检查 `.eml` 和附件。
4. Alice 使用垃圾邮件模板发送，Bob 接收后在 Spam 查看。
5. Alice 在 Sent / Recall 选择普通邮件并撤回。
6. Bob 在 Recall Notifications 查看通知，确认原邮件不再位于 inbox。
7. 在 TLS & Model 页面展示加密模式和 SVM 模型状态。
