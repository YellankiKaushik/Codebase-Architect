import express from "express";
import { CheckoutController } from "../controllers/checkout-controller";

const router = express.Router();
const controller = new CheckoutController();

router.post("/checkout", controller.checkout);

export { router };
