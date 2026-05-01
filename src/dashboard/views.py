import json

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .mission_control import (
    get_calendar_events_for_user,
    get_mission_control_payload,
    get_selected_user,
    get_tasks_for_user,
    update_task_completion_status,
)


@login_required
def home(request):
    return render(request, "dashboard/home.html")


@login_required
@ensure_csrf_cookie
def mission_control(request: HttpRequest) -> HttpResponse:
    return render(request, "dashboard/mission_control.html")


@login_required
@require_GET
def mission_control_bootstrap(request: HttpRequest) -> JsonResponse:
    return JsonResponse(get_mission_control_payload())


@login_required
@require_GET
def mission_control_tasks(request: HttpRequest) -> JsonResponse:
    user = get_selected_user()
    if user is None:
        return JsonResponse({"tasks": [], "user": None})
    return JsonResponse(
        {
            "tasks": get_tasks_for_user(user.id),
            "user": {"id": user.id, "email": user.email},
        }
    )


@login_required
@require_GET
def mission_control_calendar(request: HttpRequest) -> JsonResponse:
    user = get_selected_user()
    if user is None:
        return JsonResponse({"calendarEvents": [], "timezone": None, "user": None})
    return JsonResponse(
        {
            "calendarEvents": get_calendar_events_for_user(user.id, user.timezone),
            "timezone": user.timezone,
            "user": {"id": user.id, "email": user.email},
        }
    )


@login_required
@require_POST
def mission_control_update_task(request: HttpRequest, task_id: str) -> JsonResponse:
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    target_status = payload.get("completionStatus")
    if not isinstance(target_status, str):
        return JsonResponse({"error": "completionStatus is required"}, status=400)

    try:
        task = update_task_completion_status(task_id, target_status)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except LookupError as exc:
        return JsonResponse({"error": str(exc)}, status=404)

    return JsonResponse({"task": task})
