from __future__ import annotations

import os
import smtplib
import json
from email.message import EmailMessage
from uuid import uuid4

from sqlalchemy import delete, select

from ..data import iso_now
from ..db import DeliveryRecord, ReportDeliveryRecord, SubscriptionRecord, session_scope
from ..schemas import EmailPreviewResult, NewsItem, NotificationDelivery, ReportEmailResult, Subscription, SubscriptionRequest
from .reports import get_research_report, read_report_file

IMPACT_RANK = {"low": 1, "medium": 2, "high": 3}


def clear_notification_state() -> None:
    with session_scope() as session:
        session.execute(delete(DeliveryRecord))
        session.execute(delete(SubscriptionRecord))


def to_subscription(record: SubscriptionRecord) -> Subscription:
    return Subscription(
        id=record.id,
        email=record.email,
        country=record.country,
        topic=record.topic,
        frequency=record.frequency,
        min_impact=record.min_impact,
        created_at=record.created_at,
    )


def to_delivery(record: DeliveryRecord) -> NotificationDelivery:
    return NotificationDelivery(
        id=record.id,
        subscription_id=record.subscription_id,
        news_id=record.news_id,
        email=record.email,
        mode=record.mode,
        message=record.message,
        created_at=record.created_at,
    )


def create_subscription(request: SubscriptionRequest) -> Subscription:
    with session_scope() as session:
        existing = session.scalar(
            select(SubscriptionRecord).where(
                SubscriptionRecord.email == request.email,
                SubscriptionRecord.country == request.country,
                SubscriptionRecord.topic == request.topic,
                SubscriptionRecord.frequency == request.frequency,
                SubscriptionRecord.min_impact == request.min_impact,
            )
        )
        if existing:
            return to_subscription(existing)
        record = SubscriptionRecord(id=f"S-{uuid4().hex[:10]}", created_at=iso_now(), **request.model_dump())
        session.add(record)
        session.flush()
        return to_subscription(record)


def list_subscriptions() -> list[Subscription]:
    with session_scope() as session:
        return [to_subscription(item) for item in session.scalars(select(SubscriptionRecord).order_by(SubscriptionRecord.created_at.desc())).all()]


def list_deliveries() -> list[NotificationDelivery]:
    with session_scope() as session:
        return [to_delivery(item) for item in session.scalars(select(DeliveryRecord).order_by(DeliveryRecord.created_at.desc())).all()]


def send_email_or_preview(email: str, news_title: str | None = None) -> EmailPreviewResult:
    subject = f"[AtlasIQ] {news_title or '德国光伏市场：新的监测动态'}"
    body = "AtlasIQ 检测到一条匹配订阅规则的市场动态。请打开工作台查看证据、影响卡和后续动作。"
    host = os.getenv("SMTP_HOST")
    sender = os.getenv("SMTP_FROM")
    if not host or not sender:
        return EmailPreviewResult(
            mode="preview",
            subject=subject,
            message="SMTP 尚未配置，已生成安全预览；不会发送真实邮件。",
        )
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = email
    message.set_content(body)
    try:
        with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=10) as client:
            if os.getenv("SMTP_USERNAME"):
                client.starttls()
                client.login(os.environ["SMTP_USERNAME"], os.environ.get("SMTP_PASSWORD", ""))
            client.send_message(message)
        return EmailPreviewResult(mode="sent", subject=subject, message="邮件已发送。")
    except (OSError, smtplib.SMTPException) as error:
        return EmailPreviewResult(mode="preview", subject=subject, message=f"SMTP 发送失败，保留安全预览：{error}")


def report_email_subject(report_id: str) -> str:
    report = get_research_report(report_id)
    if report is None:
        raise ValueError("Research report not found")
    return f"[AtlasIQ] {report.profile_id.upper()} renewable-energy market brief"


def report_attachment_paths(report_id: str, formats: list[str]) -> list:
    unique_formats = list(dict.fromkeys(formats))
    files = [read_report_file(report_id, format) for format in unique_formats]
    if any(file_path is None for file_path in files):
        raise ValueError("Research report file not found")
    return [file_path for file_path in files if file_path is not None]


def save_report_delivery(report_id: str, email: str, mode: str, attachments: list[str], message: str) -> None:
    with session_scope() as session:
        session.add(
            ReportDeliveryRecord(
                id=f"RD-{uuid4().hex[:10]}",
                report_id=report_id,
                email=email,
                mode=mode,
                attachments_json=json.dumps(attachments),
                message=message,
                created_at=iso_now(),
            )
        )


def preview_report_email(report_id: str, email: str, formats: list[str]) -> ReportEmailResult:
    attachments = [file_path.name for file_path in report_attachment_paths(report_id, formats)]
    result = ReportEmailResult(
        mode="preview",
        subject=report_email_subject(report_id),
        message="安全预览已生成；报告附件不会自动发送。",
        attachments=attachments,
    )
    save_report_delivery(report_id, email, result.mode, result.attachments, result.message)
    return result


def send_report_email(report_id: str, email: str, formats: list[str]) -> ReportEmailResult:
    attachments = report_attachment_paths(report_id, formats)
    attachment_names = [file_path.name for file_path in attachments]
    subject = report_email_subject(report_id)
    host = os.getenv("SMTP_HOST")
    sender = os.getenv("SMTP_FROM")
    if not host or not sender:
        result = ReportEmailResult(
            mode="preview",
            subject=subject,
            message="SMTP 尚未配置，已生成安全预览；不会发送真实邮件。",
            attachments=attachment_names,
        )
        save_report_delivery(report_id, email, result.mode, result.attachments, result.message)
        return result
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = email
    message.set_content("AtlasIQ research report is attached. Please review the evidence and scenario assumptions before acting.")
    for file_path in attachments:
        media_type, subtype = ("application", "pdf") if file_path.suffix == ".pdf" else (
            "application",
            "vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        message.add_attachment(file_path.read_bytes(), maintype=media_type, subtype=subtype, filename=file_path.name)
    try:
        with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=10) as client:
            if os.getenv("SMTP_USERNAME"):
                client.starttls()
                client.login(os.environ["SMTP_USERNAME"], os.environ.get("SMTP_PASSWORD", ""))
            client.send_message(message)
        result = ReportEmailResult(mode="sent", subject=subject, message="报告邮件已发送。", attachments=attachment_names)
    except (OSError, smtplib.SMTPException) as error:
        result = ReportEmailResult(
            mode="failed",
            subject=subject,
            message=f"SMTP 发送失败；报告仍可下载：{error}",
            attachments=attachment_names,
        )
    save_report_delivery(report_id, email, result.mode, result.attachments, result.message)
    return result


def dispatch_for_news(items: list[NewsItem]) -> list[NotificationDelivery]:
    deliveries: list[NotificationDelivery] = []
    for item in items:
        for subscription in list_subscriptions():
            if subscription.frequency != "immediate":
                continue
            if IMPACT_RANK[item.impact] < IMPACT_RANK[subscription.min_impact]:
                continue
            result = send_email_or_preview(subscription.email, item.title)
            delivery = NotificationDelivery(
                id=f"D-{uuid4().hex[:10]}",
                subscription_id=subscription.id,
                news_id=item.id,
                email=subscription.email,
                mode="sent" if result.mode == "sent" else "preview",
                message=result.message,
                created_at=iso_now(),
            )
            with session_scope() as session:
                session.add(DeliveryRecord(**delivery.model_dump()))
            deliveries.append(delivery)
    return deliveries
