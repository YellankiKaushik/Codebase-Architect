import { on } from "./bus";
import { recordOrder } from "./service";

on("order.created", handleOrderCreated);

export function handleOrderCreated(event) {
  return recordOrder(event);
}
