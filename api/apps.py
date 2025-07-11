from django.apps import AppConfig
import logging
from django.db.models.signals import post_migrate # Import post_migrate signal
from datetime import timedelta # Import for setting run_at time
from django.utils import timezone # Import timezone for timezone-aware datetimes
import json # Import json module to create empty JSON string

logger = logging.getLogger(__name__)

class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        # Connect the schedule_background_tasks function to the post_migrate signal
        # This ensures tasks are scheduled only after migrations have run and apps are ready.
        post_migrate.connect(self.schedule_background_tasks, sender=self)

    def schedule_background_tasks(self, sender, **kwargs):
        # This function will be called by the post_migrate signal.
        # It ensures that the database is ready for queries.
        
        # Import Task model.
        from background_task.models import Task
        
        # Import both tasks
        from .tasks import update_bch_price_task, monitor_bch_addresses_task

        logger.info("Attempting to schedule background tasks via post_migrate signal...")

        try:
            # Define task names as strings (full path to the task function)
            task_name_price = 'api.tasks.update_bch_price_task'
            task_name_monitor = 'api.tasks.monitor_bch_addresses_task'

            # Calculate initial run time (e.g., 10 seconds from now)
            # Use timezone.now() to create a timezone-aware datetime
            initial_run_at = timezone.now() + timedelta(seconds=10)

            # Define empty JSON parameters for tasks that don't take arguments
            empty_json_params = json.dumps([[], {}]) 

            # Check for update_bch_price_task
            if not Task.objects.filter(task_name=task_name_price).exists():
                # Directly create a Task object, explicitly setting task_params
                Task.objects.create(
                    task_name=task_name_price,
                    run_at=initial_run_at,
                    repeat=60, # Every 60 seconds
                    repeat_until=None, # Run indefinitely
                    task_params=empty_json_params 
                )
                logger.info(f"Scheduled {task_name_price}.")
            else:
                logger.info(f"{task_name_price} already scheduled.")
            
            # Check for monitor_bch_addresses_task
            if not Task.objects.filter(task_name=task_name_monitor).exists():
                # Directly create a Task object, explicitly setting task_params
                Task.objects.create(
                    task_name=task_name_monitor,
                    run_at=initial_run_at,
                    repeat=30, # Every 30 seconds
                    repeat_until=None, # Run indefinitely
                    task_params=empty_json_params 
                )
                logger.info(f"Scheduled {task_name_monitor}.")
            else:
                logger.info(f"{task_name_monitor} already scheduled.")
                
        except Exception as e:
            logger.error(f"Error scheduling background tasks in post_migrate: {e}")

