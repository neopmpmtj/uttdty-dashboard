from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from typing import Any
from zoneinfo import ZoneInfo

from django.db import connection, transaction
from django.utils import timezone


VISIBLE_TASK_STATUSES = {"open", "in_progress", "on_hold", "done"}
WRITABLE_TASK_STATUSES = {"open", "in_progress", "done"}
DEFAULT_TIMEZONE = "Europe/Lisbon"


@dataclass(frozen=True)
class MissionControlUser:
    id: int
    email: str
    first_name: str
    last_name: str
    timezone: str


def _dict_fetchall(cursor) -> list[dict[str, Any]]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _serialize_value(value: Any) -> Any:
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return value


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _serialize_value(value) for key, value in row.items()}


def _local_day_bounds(day: date, tz_name: str) -> tuple[datetime, datetime]:
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo(DEFAULT_TIMEZONE)
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = start + timedelta(days=1)
    return start.astimezone(dt_timezone.utc), end.astimezone(dt_timezone.utc)


def get_selected_user() -> MissionControlUser | None:
    """Pick the personal user with the most Phase 1 data, excluding superusers first."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH task_counts AS (
                SELECT r.user_id, COUNT(i.*) AS task_count
                FROM managed_lists_todorecord r
                JOIN managed_lists_todoitem i ON i.todo_record_id = r.id
                WHERE COALESCE(i.is_deleted, false) = false
                  AND i.deleted_at IS NULL
                  AND i.completion_status <> 'cancelled'
                GROUP BY r.user_id
            ),
            legacy_events AS (
                SELECT user_id, COUNT(*) AS legacy_event_count
                FROM calendar_parser_calendarevent
                WHERE COALESCE(is_deleted, false) = false
                  AND deleted_at IS NULL
                GROUP BY user_id
            ),
            batch_events AS (
                SELECT r.user_id, COUNT(e.*) AS batch_event_count
                FROM batch_calendar_batchcalendarrequest r
                JOIN batch_calendar_batchcalendarevent e ON e.batch_request_id = r.id
                WHERE COALESCE(r.is_deleted, false) = false
                  AND r.deleted_at IS NULL
                GROUP BY r.user_id
            ),
            ranked_users AS (
                SELECT
                    u.id,
                    u.email,
                    u.first_name,
                    u.last_name,
                    COALESCE(NULLIF(p.timezone, ''), %s) AS timezone,
                    COALESCE(t.task_count, 0) AS task_count,
                    COALESCE(l.legacy_event_count, 0) AS legacy_event_count,
                    COALESCE(b.batch_event_count, 0) AS batch_event_count,
                    CASE WHEN u.is_superuser THEN 1 ELSE 0 END AS superuser_rank
                FROM accounts_customuser u
                LEFT JOIN accounts_userpreferences p ON p.user_id = u.id
                LEFT JOIN task_counts t ON t.user_id = u.id
                LEFT JOIN legacy_events l ON l.user_id = u.id
                LEFT JOIN batch_events b ON b.user_id = u.id
                WHERE u.is_active = true
            )
            SELECT id, email, first_name, last_name, timezone
            FROM ranked_users
            ORDER BY
                superuser_rank ASC,
                (task_count + legacy_event_count + batch_event_count) DESC,
                id ASC
            LIMIT 1
            """,
            [DEFAULT_TIMEZONE],
        )
        row = cursor.fetchone()
    if row is None:
        return None
    return MissionControlUser(
        id=row[0],
        email=row[1],
        first_name=row[2],
        last_name=row[3],
        timezone=row[4] or DEFAULT_TIMEZONE,
    )


def get_tasks_for_user(user_id: int) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                i.id::text AS id,
                i.text,
                i.description,
                i.priority,
                i.completion_status,
                i.due_date,
                i.due_time,
                i.topic,
                i.subtopic,
                i.entity_name,
                i.entity_type,
                i.created_at,
                i.completed_at,
                r.record_name,
                r.id::text AS todo_record_id
            FROM managed_lists_todoitem i
            JOIN managed_lists_todorecord r ON r.id = i.todo_record_id
            WHERE r.user_id = %s
              AND COALESCE(i.is_deleted, false) = false
              AND i.deleted_at IS NULL
              AND COALESCE(r.is_deleted, false) = false
              AND r.deleted_at IS NULL
              AND i.completion_status = ANY(%s)
            ORDER BY
              CASE i.completion_status
                WHEN 'open' THEN 1
                WHEN 'in_progress' THEN 2
                WHEN 'on_hold' THEN 3
                WHEN 'done' THEN 4
                ELSE 5
              END,
              i.due_date NULLS LAST,
              i.due_time NULLS LAST,
              i.priority DESC NULLS LAST,
              i.created_at DESC
            """,
            [user_id, list(VISIBLE_TASK_STATUSES)],
        )
        rows = _dict_fetchall(cursor)
    return [_serialize_row(row) for row in rows]


def get_calendar_events_for_user(user_id: int, tz_name: str) -> list[dict[str, Any]]:
    today = timezone.localtime(timezone.now(), ZoneInfo(tz_name)).date()
    start_utc, _ = _local_day_bounds(today, tz_name)
    _, end_utc = _local_day_bounds(today + timedelta(days=1), tz_name)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                id::text AS id,
                'legacy' AS source_type,
                'calendar_parser_calendarevent' AS source_table,
                summary,
                description,
                location,
                start_datetime,
                end_datetime,
                timezone,
                status,
                error_message,
                html_link,
                created_at
            FROM calendar_parser_calendarevent
            WHERE user_id = %s
              AND COALESCE(is_deleted, false) = false
              AND deleted_at IS NULL
              AND start_datetime >= %s
              AND start_datetime < %s
            UNION ALL
            SELECT
                e.id::text AS id,
                'batch' AS source_type,
                'batch_calendar_batchcalendarevent' AS source_table,
                e.summary,
                COALESCE(e.event_data->>'description', '') AS description,
                COALESCE(e.event_data->>'location', '') AS location,
                e.start_datetime,
                e.end_datetime,
                e.timezone,
                e.status,
                e.error_message,
                e.html_link,
                e.created_at
            FROM batch_calendar_batchcalendarevent e
            JOIN batch_calendar_batchcalendarrequest r ON r.id = e.batch_request_id
            WHERE r.user_id = %s
              AND COALESCE(r.is_deleted, false) = false
              AND r.deleted_at IS NULL
              AND e.start_datetime >= %s
              AND e.start_datetime < %s
            ORDER BY start_datetime ASC, created_at ASC
            """,
            [user_id, start_utc, end_utc, user_id, start_utc, end_utc],
        )
        rows = _dict_fetchall(cursor)
    return [_serialize_row(row) for row in rows]


def get_mission_control_payload() -> dict[str, Any]:
    user = get_selected_user()
    if user is None:
        return {
            "user": None,
            "tasks": [],
            "calendarEvents": [],
            "timezone": DEFAULT_TIMEZONE,
        }
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "firstName": user.first_name,
            "lastName": user.last_name,
        },
        "tasks": get_tasks_for_user(user.id),
        "calendarEvents": get_calendar_events_for_user(user.id, user.timezone),
        "timezone": user.timezone,
    }


def update_task_completion_status(task_id: str, target_status: str) -> dict[str, Any]:
    if target_status not in WRITABLE_TASK_STATUSES:
        raise ValueError("Unsupported task status")
    user = get_selected_user()
    if user is None:
        raise ValueError("No active user available")

    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE managed_lists_todoitem i
            SET completion_status = %s,
                completed_at = CASE
                    WHEN %s = 'done' THEN COALESCE(i.completed_at, NOW())
                    ELSE NULL
                END
            FROM managed_lists_todorecord r
            WHERE i.todo_record_id = r.id
              AND r.user_id = %s
              AND i.id = %s::uuid
              AND COALESCE(i.is_deleted, false) = false
              AND i.deleted_at IS NULL
              AND COALESCE(r.is_deleted, false) = false
              AND r.deleted_at IS NULL
              AND i.completion_status <> 'cancelled'
            RETURNING
                i.id::text AS id,
                i.text,
                i.description,
                i.priority,
                i.completion_status,
                i.due_date,
                i.due_time,
                i.topic,
                i.subtopic,
                i.entity_name,
                i.entity_type,
                i.created_at,
                i.completed_at,
                r.record_name,
                r.id::text AS todo_record_id
            """,
            [target_status, target_status, user.id, task_id],
        )
        row = cursor.fetchone()
        if row is None:
            raise LookupError("Task not found")
        columns = [column[0] for column in cursor.description]
    return _serialize_row(dict(zip(columns, row)))
