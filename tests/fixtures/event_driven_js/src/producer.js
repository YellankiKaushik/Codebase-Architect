import { publish } from "./bus";

export function placeOrder(order) {
  publish("order.created", order);
}
