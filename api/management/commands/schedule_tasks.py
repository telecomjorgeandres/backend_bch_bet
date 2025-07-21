from django.core.management.base import BaseCommand
import logging
# No need to import Task model directly if we're not querying it here

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Schedules initial background tasks for the API.'

    def handle(self, *args, **options):
        logger.info("Attempting to schedule background tasks...")
        try:
            # Import tasks here to ensure Django's app registry is ready
            from api.tasks import update_bch_price_task, monitor_bch_addresses_task

            # Simply call the decorated task functions.
            # The 'background' decorator itself handles preventing duplicate tasks
            # based on their task_hash (derived from name and arguments).
            update_bch_price_task()
            logger.info("Called update_bch_price_task for scheduling (background_task handles de-duplication).")

            monitor_bch_addresses_task()
            logger.info("Called monitor_bch_addresses_task for scheduling (background_task handles de-duplication).")

        except Exception as e:
            logger.error(f"Error scheduling background tasks: {e}")
            self.stderr.write(self.style.ERROR(f"Error scheduling background tasks: {e}"))

        self.stdout.write(self.style.SUCCESS('Background tasks scheduling complete.'))

