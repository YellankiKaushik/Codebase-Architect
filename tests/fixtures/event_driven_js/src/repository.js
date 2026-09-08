export class OrderRepository {
  static save(event) {
    return client.query("insert into orders values ($1)", [event.id]);
  }
}
