# 协议说明

## SMTP

客户端使用 `smtplib.SMTP` 连接配置中的 SMTP 地址，发送标准 MIME message。服务端使用 `aiosmtpd.Controller`，在 `handle_DATA` 中读取 `envelope.mail_from`、`envelope.rcpt_tos` 和 `envelope.content` 并写入存储层。

当前 SMTP AUTH 只在客户端保留调用接口，服务端未强制认证。TODO 是在 aiosmtpd 层补 AUTH。

## POP3

项目用 `socketserver.ThreadingTCPServer` 实现最小 POP3 Server，支持 USER、PASS、STAT、LIST、RETR、DELE、QUIT。认证调用用户表；LIST/RETR 只展示当前用户 inbox 中未删除且未撤回的邮件。

客户端使用 `poplib.POP3` 连接本地 POP3 Server。

## MIME

构造侧使用 `email.message.EmailMessage`，每封邮件包含 `Message-ID` 和 `X-MailApp-Mail-ID`。解析侧使用 `email.parser.BytesParser`，优先提取 `text/plain`，只有 HTML 时返回 HTML 文本。附件提取接口会将 attachment part 保存到指定目录。

## SSL/TLS

`ssl_utils.py` 提供 server/client SSL context 和 socket 包装函数。默认不开启 SSL/TLS，后续可以在配置中加入证书路径并包装 SMTP/POP3 socket。

## 教学简化

- SMTP Server 未实现完整 AUTH。
- POP3 Server 只覆盖演示所需命令集。
- 邮件撤回只在本项目服务器内部生效，不模拟真实互联网邮件传播。
- 垃圾过滤默认使用关键词 fallback，模型训练接口已预留。
