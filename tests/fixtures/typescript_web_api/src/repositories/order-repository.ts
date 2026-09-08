export class OrderRepository {
  static save(order) {
    return db.query("insert into orders values ($1)", [order.id]);
  }
}
