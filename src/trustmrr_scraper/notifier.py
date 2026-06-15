from __future__ import annotations

import smtplib
import ssl
import sys
from dataclasses import dataclass
from email.message import EmailMessage


@dataclass
class EmailNotifier:
    host: str
    port: int
    sender: str
    recipient: str
    user: str = ""
    password: str = ""
    enabled: bool = True

    @classmethod
    def from_env(cls, env: dict[str, str], recipient: str, enabled: bool) -> "EmailNotifier":
        host = env.get("MAIL_SMTP_HOST", "127.0.0.1")
        return cls(
            host=host,
            port=int(env.get("MAIL_SMTP_PORT", "25")),
            sender=env.get("MAIL_FROM", "noreply@kisscolab.ru"),
            recipient=env.get("MAIL_TO", recipient),
            user=env.get("MAIL_USER", ""),
            password=env.get("MAIL_PASSWORD", ""),
            enabled=enabled and bool(host and recipient),
        )

    def _send(self, subject: str, text: str, html: str | None = None) -> None:
        if not self.enabled:
            return
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = f"TrustMRR Scraper <{self.sender}>"
        message["To"] = self.recipient
        message.set_content(text)
        if html:
            message.add_alternative(html, subtype="html")
        try:
            if self.port == 465:
                server = smtplib.SMTP_SSL(
                    self.host, self.port, context=ssl.create_default_context(), timeout=60
                )
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=60)
            with server:
                if self.user and self.password:
                    if self.port != 465:
                        server.starttls(context=ssl.create_default_context())
                    server.login(self.user, self.password)
                server.send_message(message)
        except Exception as exc:  # noqa: BLE001
            print(f"[notifier] не удалось отправить письмо: {exc}", file=sys.stderr)

    def started(self, target: int, enrich: bool) -> None:
        mode = "список + детали" if enrich else "только список"
        self._send(
            f"TrustMRR: старт сбора ({target} стартапов)",
            f"Начинаю сбор {target} стартапов ({mode}).",
            _html("Старт сбора", f"Начинаю сбор <b>{target}</b> стартапов ({mode})."),
        )

    def progress(self, percent: int, done: int, target: int, phase: str = "список") -> None:
        self._send(
            f"TrustMRR [{phase}]: {percent}% ({done}/{target})",
            f"Прогресс ({phase}): {percent}% ({done}/{target}).",
            _html(
                "Прогресс сбора",
                f"Фаза «{phase}»: собрано <b>{done}</b> из {target} (<b>{percent}%</b>).",
            ),
        )

    def completed(self, count: int, path: str, elapsed: float) -> None:
        self._send(
            f"TrustMRR: готово, собрано {count} стартапов",
            f"Сбор завершён.\nСтартапов: {count}\nФайл: {path}\nВремя: {elapsed:.0f} c.",
            _html(
                "Сбор завершён",
                f"Собрано <b>{count}</b> стартапов за {elapsed:.0f} c.<br>Файл: {path}",
            ),
        )

    def failed(self, error: str) -> None:
        self._send(
            "TrustMRR: ОШИБКА сбора",
            f"Сбор прерван с ошибкой:\n{error}",
            _html("Ошибка сбора", f"Сбор прерван:<br><code>{error}</code>"),
        )


def _html(title: str, message: str) -> str:
    return f"""<!doctype html>
<html lang="ru">
  <body style="margin:0;padding:0;background:#f6f8fb;font-family:Arial,Helvetica,sans-serif;color:#111827;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f6f8fb;padding:32px 16px;">
      <tr><td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 6px 24px rgba(0,0,0,0.08);">
          <tr><td style="padding:32px;">
            <div style="font-size:14px;color:#6b7280;margin-bottom:12px;">KISS Colab · TrustMRR Scraper</div>
            <h1 style="margin:0 0 16px;font-size:22px;line-height:1.3;color:#111827;">{title}</h1>
            <p style="margin:0;font-size:16px;line-height:1.6;color:#374151;">{message}</p>
          </td></tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>"""
