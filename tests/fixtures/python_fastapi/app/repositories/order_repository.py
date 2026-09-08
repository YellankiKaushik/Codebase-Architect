class OrderRepository:
    def save(self):
        session.add({"table": "orders"})
        return {"ok": True}
