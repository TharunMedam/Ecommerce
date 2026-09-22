# Anjaneya Herbals & Dry Fruits

[Live catalog preview](https://anjaneya-herbals-eight.vercel.app)

The previous Node.js portfolio demo is preserved in `legacy-demo/`. The React/Django application below is the current project.

React storefront + Django REST backend + MySQL, with an AWS deployment baseline and a Vercel storefront target. Built for bilingual English/Telugu browsing, delivery and pickup.

## Current state

- 116 editable catalog **candidates**, each with English and Telugu names. Merchant stock and most prices are unverified. Products start with zero stock and cannot be ordered until confirmed.
- Customer registration/login, password reset integration, persisted cart, transactional checkout and private order history.
- Separate staff login and dashboard: create/edit products and pack sizes, update prices/stock, set delivery rules/PIN codes/hours, manage order lifecycle, reply to customer feedback.
- Free delivery when subtotal is **strictly greater than ₹800**; merchant-editable threshold and base fee. Pickup is free. Cash on delivery is rejected by the API.
- Razorpay integration creates orders server-side, verifies callback signatures and captured amounts, supports signed webhooks, reserves inventory, expires abandoned payment reservations and flags late captures for refund review. No card/UPI credentials are stored.
- AWS Terraform baseline for EC2, private Multi-AZ RDS MySQL, private S3, CloudFront, ALB, IAM, Secrets Manager, ECR and CloudWatch alarms.
- Vercel frontend includes a same-origin API proxy to the AWS Django backend. When `AWS_BACKEND_ORIGIN` is absent, it serves a clearly labeled read-only catalog preview; sign-in and order writes do not pretend to succeed.

**Not yet a live order-taking store:** merchant details, delivery PIN codes/base fee, actual inventory, payment account, business policies and backend deployment remain to be configured. AWS credentials available during development were invalid. Do not describe this implementation as already deployed to AWS.

## Normal development with MySQL

1. Copy `.env.example` to `.env`. Set unique database passwords and a random Django secret. For **local HTTP development only**, set `DJANGO_DEBUG=1`; do not use this setting in production.
2. Build/start the database: `docker compose up -d db`.
3. Build the application images: `docker compose build`.
4. Migrate and seed: `docker compose run --rm app python manage.py migrate`, then `docker compose run --rm app python manage.py seed_catalog`.
5. Create the real owner: `docker compose run --rm app python manage.py createsuperuser`. **Use the owner's email address as the username** so the email sign-in form works. Supply a unique password interactively.
6. Start the app and storefront: `docker compose up -d app web`. Browse `http://localhost:8080`.
7. Run the test suite against MySQL: `docker compose run --rm app python manage.py test shop`. The test database user must have permission to create/drop the test database; do not grant this to the production runtime user.

Alternatively run Django with `python manage.py runserver 127.0.0.1:8000` and the frontend with `npm ci` then `npm run dev`. Vite proxies `/api` to Django. Production defaults refuse a missing secret, use MySQL, enforce HTTPS, secure cookies and HSTS.

## Vercel

Deploy **only `frontend/`**, not the repository root. `vercel.json` configures Vite and the API proxy. No database, local login credentials or private backend files belong in this upload.

- Without `AWS_BACKEND_ORIGIN`: read-only catalog preview from `api/catalog-preview.json`, with all purchase availability disabled.
- With `AWS_BACKEND_ORIGIN=https://your-django-domain`: API requests proxy to Django. Keep the Django backend HTTPS-only. Add the Vercel production URL to `CSRF_TRUSTED_ORIGINS`; set Django `ALLOWED_HOSTS` to the backend's origin hostname. Cookies remain host-only and are forwarded by the same-origin proxy.
- Keep API responses uncached. Do not place payment secrets in `VITE_*` variables or browser bundles.
- The snapshot contains only catalog candidates and provisional public store settings. Regenerate it intentionally after reviewing the merchandise; a connected backend serves live data instead.

## Owner workflow

1. Sign in through **Store owner login**.
2. In Products, edit each English/Telugu name, actual brand, pack size, selling price, SKU, available stock and your product photo URL. Confirm only merchandise actually sold by the store. Uncheck “Show in catalog” for unsuitable candidates.
3. In Store settings, confirm the pickup address, phone, opening schedule, delivery PIN codes, base delivery fee and free-delivery threshold.
4. Connect/test payments and configure email. Review customer-facing business policies. Only then enable **Accept customer orders**.
5. Orders move from placed → preparing → ready (pickup) / out for delivery → completed. Record payment received for pay-at-pickup orders. Paid online cancellations require refund handling in Razorpay; they cannot silently be marked cancelled.
6. Customer feedback stays private. Reply and mark it open/in progress/resolved from the dashboard; customers see replies in their account.

## Validation and limits

19 Django tests passed locally: permissions, CSRF, registration privilege isolation, idempotency, stock rollback, pricing changes/tampering, threshold boundary, delivery coverage, pickup hours, cancellation, feedback privacy/replies, capture matching, expiry/late capture, and payment-before-completion. A Vite production build passed using `vite.portable.config.js`, an in-process compiler configuration for this restricted Windows environment. Terraform initialization and validation passed; infrastructure was not applied.

MySQL container tests and payment-provider sandbox transactions still need to run in the deployment environment. The local Docker service was inaccessible. Payment-network operations are mocked in automated tests; this is not a claim that live payments have been tested. No AWS resources were created or billed.

See `docs/RESEARCH.md` for source links and conflicting merchant listings, `docs/AWS_DEPLOYMENT.md` for deployment steps, and `docs/ASSETS.md` for generated imagery provenance.
