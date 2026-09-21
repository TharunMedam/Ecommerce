# E-Commerce Web Application

[Live demo](https://ztm-ecommerce.vercel.app)

Runnable portfolio implementation for the resume project covering product catalog management, authentication-style sessions, cart workflows, pricing, order processing, inventory checks, and admin operations.

## Run

```powershell
cd projects/ecommerce
npm start
```

Open `http://localhost:4100`.

## API

- `GET /api/products` lists products with category and inventory filters.
- `POST /api/sessions` creates a demo user session.
- `GET /api/cart?sessionId=...` returns the current cart with totals.
- `POST /api/cart/items` adds an item to the cart.
- `POST /api/checkout` creates an order and reduces inventory.
- `GET /api/admin/orders` lists submitted orders.

The app uses an in-memory store so the project can run anywhere without local database setup. The schema and service layer mirror the normalized product, user, order, inventory, and pricing responsibilities described in the resume.

On Vercel, this is a demo only: sessions, carts, orders, and inventory changes are not durable across function restarts.

