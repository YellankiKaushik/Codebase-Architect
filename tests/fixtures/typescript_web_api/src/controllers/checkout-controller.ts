import { CheckoutService } from "@app/services/checkout-service";

export class CheckoutController {
  checkout(req, res) {
    return CheckoutService.checkout(req.body);
  }
}
