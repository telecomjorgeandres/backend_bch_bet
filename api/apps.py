# bch_betting_backend/api/apps.py
from django.apps import AppConfig
import logging
# Removed post_migrate import as we are moving scheduling to ready()
from datetime import timedelta # Import for setting run_at time
from django.utils import timezone # Import timezone for timezone-aware datetimes
import json # Import json module to create empty JSON string
from django.db.utils import OperationalError # Import for database specific errors

logger = logging.getLogger(__name__)

class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        logger.debug(f"ApiConfig ready() method called for app: {self.name}.")
        # Import Task model and tasks inside ready() to ensure apps are fully loaded
        from background_task.models import Task
        from .tasks import update_bch_price_task, monitor_bch_addresses_task

        logger.info("Attempting to schedule background tasks directly in ready()...")

        try:
            # Define task names as strings (full path to the task function)
            task_name_price = 'api.tasks.update_bch_price_task'
            task_name_monitor = 'api.tasks.monitor_bch_addresses_task'

            # Calculate initial run time (e.g., 1 second from now) for quicker startup
            initial_run_at = timezone.now() + timedelta(seconds=1) # Changed from 10 to 1 second

            # Define empty JSON parameters for tasks that don't take arguments
            # This should be a JSON-encoded list containing an empty list for args and an empty dict for kwargs
            empty_json_params = json.dumps([[], {}]) 

            # Check for update_bch_price_task
            if not Task.objects.filter(task_name=task_name_price).exists():
                logger.debug(f"Task {task_name_price} not found in DB. Attempting to create.")
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
                logger.debug(f"Task {task_name_monitor} not found in DB. Attempting to create.")
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
                    
        except OperationalError as oe:
            # This specific error indicates database connection issues or tables not ready
            logger.error(f"Database OperationalError during task scheduling: {oe}. This might happen if DB is not fully ready.", exc_info=True)
        except Exception as e:
            logger.error(f"An unexpected error occurred during task scheduling in ready(): {e}", exc_info=True)

