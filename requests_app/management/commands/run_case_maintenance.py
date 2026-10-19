from django.core.management.base import BaseCommand

from requests_app import notifications, services


class Command(BaseCommand):
    help = "Scheduled job (every 15 minutes): escalate overdue cases, auto-close confirmed ones, retry SMS."

    def handle(self, *args, **options):
        escalated = services.escalate_overdue()
        closed = services.auto_close_resolved()
        sent = notifications.send_pending()
        self.stdout.write(f"escalated={escalated} auto_closed={closed} sms_sent={sent}")
