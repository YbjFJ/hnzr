import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from config import settings

def send_verify_code_email(to_email: str, code: str, valid_minutes: int = 15) -> bool:
    if not settings.MAIL_SERVER or not settings.MAIL_USERNAME:
        print(f"[email_util] 验证码: {code}")
        return True

    subject = "【AI 咨询平台】密码重置验证码"
    body = f"您好，\n\n您正在申请重置密码，验证码为：{code}\n\n验证码有效期为 {valid_minutes} 分钟。"

    try:
        msg = MIMEText(body, "plain", "utf-8")
        
        # 1. 严格使用 formataddr 处理发件人（把没用的 encode 删掉）
        msg["From"] = formataddr(("智农金信", settings.MAIL_USERNAME))
        
        # 2. 补上这一句！严格使用 formataddr 处理收件人，对齐你成功的代码
        msg["To"] = formataddr(("", to_email))
        
        # 3. 处理主题
        msg["Subject"] = Header(subject, "utf-8")

        if settings.MAIL_USE_SSL:
            with smtplib.SMTP_SSL(settings.MAIL_SERVER, settings.MAIL_PORT) as server:
                server.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
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