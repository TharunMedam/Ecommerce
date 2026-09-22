# AWS backend deployment

This is an infrastructure baseline; Terraform has been validated but not applied. Existing AWS credentials were invalid. Provisioning creates billable EC2, RDS Multi-AZ, ALB and related resources. Review `terraform plan` and costs in the intended account before applying.

## Prerequisites

- An AWS account authenticated through your normal secure CLI/SSO flow.
- An existing VPC with two public subnets and two private database subnets across availability zones. The application subnet needs outbound connectivity through NAT or appropriate VPC endpoints for ECR, S3, Secrets Manager, SSM and CloudWatch.
- A Route53 hosted zone. Provision a regional ACM certificate covering the origin hostname and a certificate in `us-east-1` covering the CloudFront hostname. Do not substitute unverified certificate ARNs.
- Review/adjust the baseline's instance sizing, Multi-AZ cost and single-EC2 availability limit. It is not a horizontally autoscaled design.

## Deployment sequence

1. Copy `infra/terraform.tfvars.example` to an ignored `.tfvars` file and supply actual IDs/domains/certificate ARNs. Run `terraform init`, `terraform plan`, review the plan and only then `terraform apply`.
2. Build both Docker images and push immutable release tags to the Terraform-created ECR repositories. Record the image digests for rollback.
3. Through a secure DBA session, use the RDS-managed master secret to create a separate application database user with access only to the `anjaneya` schema. RDS must use utf8mb4. Do not give the EC2 role access to the master password. Use a controlled migration role if separating runtime and schema-change privileges.
4. Put application configuration in the Terraform-created Secrets Manager secret as a JSON object. Include a random `DJANGO_SECRET_KEY`, `MYSQL_HOST` from the RDS endpoint, database name/user/password, `MYSQL_SSL_CA=/app/certs/global-bundle.pem`, `DJANGO_DEBUG=0`, backend `DJANGO_ALLOWED_HOSTS`, `TRUST_PROXY=1`, `CSRF_TRUSTED_ORIGINS` including the storefront's HTTPS URL, `FRONTEND_URL`, payment secrets and SMTP settings. Set `AWS_STORAGE_BUCKET_NAME` to the created private bucket.
5. Use SSM Session Manager to access the EC2 instance; no SSH ingress is opened. Install the official Docker Compose plugin, log Docker into ECR with the instance role, and copy `compose.aws.yaml` to `/opt/anjaneya`. Retrieve the application secret into `/opt/anjaneya/app.env` with mode 0600 without printing it to terminal/logs. Supply `BACKEND_IMAGE`, `FRONTEND_IMAGE` and `AWS_REGION` in a separate mode-0600 compose environment file. If `var.name` is changed, update the log group name in the compose file too.
6. Run a one-off migration container. Collect Django static files **in the final backend image at release build time**, using temporary non-secret configuration (`DJANGO_DEBUG=1 LOCAL_SQLITE=1`) so WhiteNoise can serve admin CSS in the immutable image. Run `seed_catalog` once; it never overwrites existing merchant edits. Create a superuser interactively, using email as username.
7. Start the services and install/enable `expire-orders.timer` and its service. Check ALB target health, backend HTTPS, DB connectivity, CloudWatch logs and alarm subscription confirmation.
8. Configure Razorpay in test mode first. Enable automatic capture and add the signed `payment.captured` webhook at `/api/payments/webhook/`. Test success, failure, timeout, duplicate callback, cancellation, refunds and abandoned reservations before adding live credentials. Late captures after stock is released are flagged `refund_required` for manual review in the provider dashboard.
9. For a Vercel storefront, set its server-only `AWS_BACKEND_ORIGIN` to the working Django HTTPS origin (the CloudFront backend hostname can be used). Deploy again and verify CSRF/session cookies through the Vercel proxy. Public frontend and API must use the same origin from the browser's perspective.
10. Run the MySQL test suite and an actual test-mode checkout. Confirm merchant catalog, fees/PIN codes, pickup hours, business policies and SMTP before accepting customer orders.

## Cloud resources

EC2 runs Django/Gunicorn behind nginx and an HTTPS ALB. CloudFront uses HTTPS to the ALB and never caches session/API responses. Immutable `/assets/` files can be cached. The ALB only accepts the AWS CloudFront origin-facing network range; the EC2 application port only accepts the ALB security group. RDS accepts only the app security group and is private/encrypted. The EC2 IAM role can read only the app secret, access its media bucket, pull its two ECR repositories, write its CloudWatch logs and use SSM. RDS backups are retained 14 days and deletion protection is on.

S3 is configured as Django's private media storage. Current product editing accepts an image URL, so using your own signed S3 media URLs needs an upload/delivery workflow and URL refresh strategy before relying on expiring URLs in catalog records. Public product assets can instead be served through a separately configured CloudFront media origin with appropriate bucket access policy. Do not disable the bucket's public-access protections to fix image access.

## Operational limitations

- The built-in DRF throttle cache is process-local. Put shared throttling (Redis or an upstream WAF/rate limiter) in place before public account registration at scale.
- Customer email verification and transactional order notifications are not implemented; password reset delivery requires SMTP configuration.
- Paid refunds are intentionally manual in the payment-provider dashboard; refund execution/reconciliation automation is not implemented.
- No tax calculator, courier integration, GST invoice engine or prescription fulfilment workflow is included. Selling prices are the merchant-entered customer prices. Review actual merchandise and tax/policy requirements before launch.
- Reconcile provider-created orders after rare network/DB commit failures. Use monitoring for unpaid and `refund_required` orders.
- Configure offsite operational alerting, retention/deletion policy, backup restoration tests and your merchant terms before accepting real orders.

These limitations are concrete launch/operations work, not assertions of a completed AWS production deployment.
