from django.core.management.base import BaseCommand
from shop.services import expire_orders
class Command(BaseCommand):
    help='Release stock reserved by unpaid orders after twenty minutes; schedule every minute.'
    def handle(self,*args,**options): expire_orders()
