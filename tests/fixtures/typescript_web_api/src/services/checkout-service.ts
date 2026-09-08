import { OrderRepository } from "../repositories/order-repository";

export class CheckoutService {
  static checkout(payload) {
    return OrderRepository.save(payload);
  }
}
