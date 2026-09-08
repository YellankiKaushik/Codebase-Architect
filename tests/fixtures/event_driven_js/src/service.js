import { OrderRepository } from "./repository";

export function recordOrder(event) {
  return OrderRepository.save(event);
}
