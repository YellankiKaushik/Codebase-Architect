from app.repositories.order_repository import OrderRepository

class CheckoutService:
    def checkout(self):
        repo = OrderRepository()
        return repo.save()
