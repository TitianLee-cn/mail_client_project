# 协议实现说明

## SMTP（RFC 5321）

- 客户端使用 `smtplib`，服务端使用 `aiosmtpd`。
- 支持 EHLO、MAIL、RCPT、DATA、QUIT 及 SMTPUTF8。
- 支持 `AUTH PLAIN` 和 `AUTH LOGIN`，账号由 SQLite 用户表校验。
- 默认要求先执行 STARTTLS，再允许 AUTH 和邮件传输。
- `MAIL FROM` 必须与已认证用户一致，避免发件人伪造。
- SMTP DATA 的 CRLF、结束标记和透明传输由标准库及 `aiosmtpd` 处理。

## POP3（RFC 1939）

服务端实现 AUTHORIZATION、TRANSACTION、UPDATE 三种状态，支持：

- USER、PASS、STAT、LIST、LIST n、RETR、DELE、NOOP、RSET、QUIT。
- UIDL、CAPA 和 STLS 扩展。
- 登录成功时建立稳定 maildrop 快照，消息编号在当前会话内不变化。
- DELE 只记录会话内删除标记；QUIT 进入 UPDATE 状态后统一提交。
- 异常断开或 RSET 不会提交删除。
- RETR 输出统一使用 CRLF，并对以点开头的正文行执行 dot-stuffing。
- 未认证用户不能执行事务状态命令。
- 默认必须先 STLS 才能发送 USER/PASS 密码。

## MIME（RFC 2045）

- 使用 `email.message.EmailMessage` 构建邮件。
- 纯文本使用 `text/plain`；HTML 使用 `multipart/alternative`，同时提供文本回退。
- 附件根据文件类型设置 Content-Type，由标准库完成 Base64 等传输编码。
- 使用 `BytesParser(policy=policy.default)` 解码正文和附件。
- 附件保存时去除目录部分并处理重名，防止路径穿越和覆盖。
- 每封邮件同时具有标准 Message-ID、客户端 MIME ID 和服务端 UIDL/mail_id。

## TLS

- SMTP 默认 STARTTLS，POP3 默认 STLS。
- 服务端和客户端最低使用 TLS 1.2。
- 默认演示证书包含 `localhost` 和 `127.0.0.1` SAN。
- 可执行 `scripts/generate_dev_cert.sh` 重新生成十年期课程演示证书。
- 演示私钥只能用于本地课程环境，生产部署必须替换。

## 教学边界

邮件撤回只在本项目服务器控制的邮箱内生效，无法撤回已经投递到外部邮件系统的邮件。
