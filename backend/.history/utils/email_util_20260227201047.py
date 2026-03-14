import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from config import settings

def send_verify_code_email(to_email: str, code: str, valid_minutes: int = 15) -> bool:
    """发送验证码邮件。若未配置 MAIL_SERVER/MAIL_USERNAME 则打印到控制台并返回 True。"""
    if not settings.MAIL_SERVER or not settings.MAIL_USERNAME:
        print(f"[email_util] 未配置邮件，验证码仅打印: 发送至 {to_email} 的验证码为: {code}，{valid_minutes} 分钟有效")
        return True

    subject = "【AI 咨询平台】密码重置验证码"
    body = f"""您好，

您正在申请重置密码，验证码为：{code}

验证码有效期为 {valid_minutes} 分钟，请勿泄露给他人。

如非本人操作，请忽略本邮件。
"""
    try:
        # 1. 显式指定正文为 utf-8 编码的 MIMEText
        msg = MIMEText(body, "plain", "utf-8")

        # 2. 对包含中文的邮件主题进行显式的 Header 编码
        msg["Subject"] = Header(subject, "utf-8")

        # 3. 规范发件人格式，并给发件人加上一个友好的中文昵称（同样需编码）
        # 这样用户收到的邮件发件人会显示为 "智农金信" 而不是一串干巴巴的邮箱号
        sender_name = Header("智农金信", "utf-8").encode()
        msg["From"] = formataddr(("智农金信", settings.MAIL_USERNAME))
        
        # 收件人邮箱通常是纯英文字符，直接赋值即可
        msg["To"] = to_email

        if settings.MAIL_USE_SSL:
            with smtplib.SMTP_SSL(settings.MAIL_SERVER, settings.MAIL_PORT) as server:
                server.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
                # 放弃 send_message，直接使用底层的 sendmail 配合 as_string()
                server.sendmail(settings.MAIL_USERNAME, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(settings.MAIL_SERVER, settings.MAIL_PORT) as server:
                server.starttls()
                server.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
                server.sendmail(settings.MAIL_USERNAME, [to_email], msg.as_string())
        return True
    except Exception as e:
        print(f"[email_util] 发送邮件失败: {e}")
        return False