const assert = require("assert");
const { createStore } = require("./data-store");

const store = createStore();
const session = store.createSession({
  name: "Tharun",
  email: "tharun@example.com"
});

assert.ok(session.sessionId);
assert.strictEqual(store.listProducts({ category: "apparel" }).length, 1);

const cart = store.addCartItem({
  sessionId: session.sessionId,
  productId: "sku-cloud-hoodie",
  quantity: 2
});

assert.strictEqual(cart.items.length, 1);
assert.strictEqual(cart.items[0].lineTotal, 109.98);
assert.ok(cart.totals.grandTotal > cart.totals.subtotal);

const order = store.checkout({
  sessionId: session.sessionId,
  address: "Cincinnati, OH"
});

assert.strictEqual(order.status, "submitted");
assert.strictEqual(store.getCart(session.sessionId).items.length, 0);
assert.strictEqual(store.listOrders().length, 1);

console.log("ecommerce data-store tests passed");
