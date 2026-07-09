from django.db import transaction

class TransactionManager:
    @staticmethod
    def execute(func):
        def wrapper(*args, **kwargs):
            with transaction.atomic():
                return func(*args, **kwargs)
        return wrapper
