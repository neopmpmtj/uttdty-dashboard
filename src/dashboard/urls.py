from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("mission-control/", views.mission_control, name="mission_control"),
    path(
        "mission-control/api/bootstrap/",
        views.mission_control_bootstrap,
        name="mission_control_bootstrap",
    ),
    path(
        "mission-control/api/tasks/",
        views.mission_control_tasks,
        name="mission_control_tasks",
    ),
    path(
        "mission-control/api/calendar/",
        views.mission_control_calendar,
        name="mission_control_calendar",
    ),
    path(
        "mission-control/api/tasks/<uuid:task_id>/status/",
        views.mission_control_update_task,
        name="mission_control_update_task",
    ),
]
