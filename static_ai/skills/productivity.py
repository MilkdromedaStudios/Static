"""Useful local actions with portable outputs. No email or calendar account access."""

import csv
import io
import math
import statistics
from datetime import datetime, timezone
from email.message import EmailMessage

from pydantic import Field, model_validator

from ..config import StrictModel
from ..db import uid
from .base import Skill


class CalendarEvent(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    start: datetime
    end: datetime
    description: str = Field(default="", max_length=10000)
    location: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def times(self):
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("Use explicit timezone offsets for start and end")
        if self.end <= self.start:
            raise ValueError("The event must end after it starts")
        return self


class EmailDraft(StrictModel):
    subject: str = Field(min_length=1, max_length=200, pattern=r"^[^\r\n]+$")
    body: str = Field(min_length=1, max_length=30000)
    to: str = Field(default="", max_length=300, pattern=r"^[^\r\n]*$")


class TableAnalysis(StrictModel):
    artifact_id: str = Field(min_length=1, max_length=100)


def ical_text(value):
    return (
        value.replace("\\", "\\\\")
        .replace("\r", "")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def fold_line(value):
    # RFC 5545 folds at 75 octets without splitting a Unicode character.
    lines, current = [], ""
    for char in value:
        if len((current + char).encode("utf-8")) > 75:
            lines.append(current)
            current = " "
        current += char
    return "\r\n".join([*lines, current])


async def calendar(ctx, args):
    def stamp(dt):
        return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Static//Personal workspace//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid()}@static.local",
        f"DTSTAMP:{stamp(datetime.now(timezone.utc))}",
        f"DTSTART:{stamp(args.start)}",
        f"DTEND:{stamp(args.end)}",
        "SUMMARY:" + ical_text(args.title),
        "DESCRIPTION:" + ical_text(args.description),
        "LOCATION:" + ical_text(args.location),
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    data = ("\r\n".join(fold_line(line) for line in lines) + "\r\n").encode("utf-8")
    artifact = ctx.artifacts.save(
        ctx.conversation_id, ctx.run_id, args.title + ".ics", data, "text/calendar"
    )
    return {
        **artifact,
        "note": "Prepared a calendar file. The user must import it; no event has been booked or added to an account.",
    }


async def email(ctx, args):
    message = EmailMessage()
    message["Subject"] = args.subject
    if args.to:
        message["To"] = args.to
    message["X-Unsent"] = "1"
    message.set_content(args.body)
    artifact = ctx.artifacts.save(
        ctx.conversation_id, ctx.run_id, args.subject + ".eml", message.as_bytes(), "message/rfc822"
    )
    return {
        **artifact,
        "note": "Saved an unsent email draft. Review in an email client before sending; no email was sent.",
    }


async def analyze(ctx, args):
    item = ctx.artifacts.get(args.artifact_id, ctx.conversation_id)
    if not item["name"].lower().endswith(".csv"):
        raise ValueError("Choose a CSV artifact")
    text = ctx.artifacts.text(args.artifact_id, ctx.conversation_id)
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 2:
        raise ValueError("The CSV needs a header and at least one row")
    if len(rows[0]) > 100:
        raise ValueError("CSV analysis supports up to 100 columns")
    headers, data = rows[0], rows[1:]
    columns = []
    for index, header in enumerate(headers):
        values = [row[index].strip() if index < len(row) else "" for row in data]
        numbers = []
        for value in values:
            try:
                number = float(value)
                if math.isfinite(number):
                    numbers.append(number)
            except ValueError:
                continue
        summary = {
            "name": header,
            "nonempty": sum(bool(v) for v in values),
            "numeric": len(numbers),
        }
        if numbers:
            total = math.fsum(numbers)
            if not math.isfinite(total):
                raise ValueError("Numeric values exceed the supported range")
            summary.update(
                min=min(numbers), max=max(numbers), sum=total, mean=statistics.mean(numbers)
            )
        columns.append(summary)
    return {
        "rows": len(data),
        "columns": columns,
        "scope": "The first 30,000 characters of the file. Numeric statistics exclude empty, nonnumeric and nonfinite values; no currency or locale inference.",
    }


def register(registry):
    registry.add(
        Skill(
            "calendar_create",
            "Create a downloadable .ics calendar event. Ask for timezone if unknown. This does not book anything or change an online calendar.",
            "Organize",
            CalendarEvent,
            calendar,
        )
    )
    registry.add(
        Skill(
            "email_draft",
            "Create an unsent .eml email draft for the user to review and send themselves. No account access or email sending.",
            "Organize",
            EmailDraft,
            email,
        )
    )
    registry.add(
        Skill(
            "table_analyze",
            "Compute row counts and numeric column summaries from an uploaded CSV artifact in this conversation. Up to the first 30,000 characters; no code execution.",
            "Research",
            TableAnalysis,
            analyze,
        )
    )
