import smtplib
from email.message import EmailMessage
from config import settings


def send_verify_code_email(to_email: str, code: str, valid_minutes: int = 15) -> bool:
    """发送验证码邮件。若未配置 MAIL_SERVER/MAIL_USERNAME 则打印到控制台并返回 True。"""
    subject = "【AI 咨询平台】密码重置验证码"
    body = f"""您好，

您正在申请重置密码，验证码为：{code}

验证码有效期为 {valid_minutes} 分钟，请勿泄露给他人。

如非本人操作，请忽略本邮件。
"""
    if not settings.MAIL_SERVER or not settings.MAIL_USERNAME:
        print(f"[email_util] 未配置邮件，验证码仅打印: 发送至 {to_email} 的验证码为: {code}，{valid_minutes} 分钟有效")
        return True

    from_addr = settings.MAIL_USERNAME
    try:
        # 使用现代的 EmailMessage，默认使用现代策略，完美支持中文
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_email
        msg.set_content(body) # 默认作为 plain text 和 utf-8 处理

        if settings.MAIL_USE_SSL:
            with smtplib.SMTP_SSL(settings.MAIL_SERVER, settings.MAIL_PORT) as server:
                server.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
                # 直接使用 send_message，不需要手动转换为 Bytes
                server.send_message(msg)
        else:
            with smtplib.SMTP(settings.MAIL_SERVER, settings.MAIL_PORT) as server:
                server.starttls()
                server.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
                server.send_message(msg)
        return True
    except Exception as e:
        print(f"[email_util] 发送邮件失败: {e}")
        return False