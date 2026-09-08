from fastapi import FastAPI
from app.services.checkout_service import CheckoutService

app = FastAPI()

@app.post("/checkout")
def checkout():
    return CheckoutService().checkout()
