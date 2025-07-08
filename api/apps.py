# api/apps.py

from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        # Import the task function here to avoid circular imports
        # This ensures the app registry is ready before importing tasks
        from .tasks import update_bch_price_task

        # Check if the task is already scheduled to prevent multiple schedules on reload
        # This is important for development server reloads
        from background_task.models import Task
        if not Task.objects.filter(task_name='api.tasks.update_bch_price_task').exists():
            # Schedule the task to run for the first time
            # It will then reschedule itself every 60 seconds
            update_bch_price_task(repeat=60, repeat_until=None) # repeat_until=None means run indefinitely
            print("BCH price update task scheduled.")
        else:
            print("BCH price update task already scheduled.")