terraform {

  required_version = ">= 1.6"
  required_providers {

    aws = {
      source = "hashicorp/aws", version = "~> 5.0"
    }

  }

}
provider "aws" {
  region = var.region
}
variable "region" {
  default = "ap-south-1"
}
variable "name" {
  default = "anjaneya-store"
}
variable "vpc_id" {
  type = string
}
variable "public_subnet_ids" {
  type = list(string)
}
variable "private_subnet_ids" {
  type = list(string)
}
variable "app_subnet_id" {
  type = string
}
variable "hosted_zone_id" {
  type = string
}
variable "domain" {
  type = string
}
variable "origin_domain" {
  type = string
}
variable "origin_certificate_arn" {
  type = string
}
variable "cloudfront_certificate_arn" {
  type = string
}
variable "alarm_email" {
  type = string
}

data "aws_caller_identity" "current" {

}
data "aws_ssm_parameter" "ami" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}
data "aws_ec2_managed_prefix_list" "cloudfront" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}
data "aws_cloudfront_cache_policy" "disabled" {
  name = "Managed-CachingDisabled"
}
data "aws_cloudfront_cache_policy" "assets" {
  name = "Managed-CachingOptimized"
}
data "aws_cloudfront_origin_request_policy" "viewer" {
  name = "Managed-AllViewer"
}

resource "aws_security_group" "alb" {

  name   = "${var.name}-alb"
  vpc_id = var.vpc_id
  ingress {

    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    prefix_list_ids = [data.aws_ec2_managed_prefix_list.cloudfront.id]

  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

}
resource "aws_security_group" "app" {

  name   = "${var.name}-app"
  vpc_id = var.vpc_id
  ingress {
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

}
resource "aws_security_group" "db" {

  name   = "${var.name}-db"
  vpc_id = var.vpc_id
  ingress {
    from_port       = 3306
    to_port         = 3306
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }

}
resource "aws_db_subnet_group" "store" {

  name       = var.name
  subnet_ids = var.private_subnet_ids

}
resource "aws_db_instance" "store" {

  identifier                      = var.name
  engine                          = "mysql"
  engine_version                  = "8.4"
  instance_class                  = "db.t4g.micro"
  allocated_storage               = 20
  max_allocated_storage           = 100
  storage_encrypted               = true
  db_name                         = "anjaneya"
  username                        = "storeadmin"
  manage_master_user_password     = true
  db_subnet_group_name            = aws_db_subnet_group.store.name
  vpc_security_group_ids          = [aws_security_group.db.id]
  publicly_accessible             = false
  multi_az                        = true
  backup_retention_period         = 14
  deletion_protection             = true
  skip_final_snapshot             = false
  final_snapshot_identifier       = "${var.name}-final"
  enabled_cloudwatch_logs_exports = ["error", "slowquery"]

}
resource "aws_s3_bucket" "media" {
  bucket = "${var.name}-media-${data.aws_caller_identity.current.account_id}"
}
resource "aws_s3_bucket_public_access_block" "media" {

  bucket                  = aws_s3_bucket.media.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true

}
resource "aws_s3_bucket_versioning" "media" {

  bucket = aws_s3_bucket.media.id
  versioning_configuration {
    status = "Enabled"
  }

}
resource "aws_s3_bucket_server_side_encryption_configuration" "media" {

  bucket = aws_s3_bucket.media.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }

}
resource "aws_secretsmanager_secret" "app" {

  name                    = "${var.name}/application"
  recovery_window_in_days = 30
  description             = "Application environment JSON. Set values after creating the least-privilege database user; never commit secrets."

}
resource "aws_ecr_repository" "app" {

  name                 = "${var.name}-backend"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }

}
resource "aws_ecr_repository" "web" {

  name                 = "${var.name}-frontend"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }

}
resource "aws_cloudwatch_log_group" "app" {
  name              = "/${var.name}/containers"
  retention_in_days = 30
}
resource "aws_iam_role" "ec2" {

  name = "${var.name}-ec2"
  assume_role_policy = jsonencode({
    Version = "2012-10-17", Statement = [{
      Effect = "Allow", Principal = {
        Service = "ec2.amazonaws.com"
      }, Action = "sts:AssumeRole"
    }]
  })

}
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}
resource "aws_iam_role_policy" "app" {

  role = aws_iam_role.ec2.id
  policy = jsonencode({
    Version = "2012-10-17", Statement = [
      {
        Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = aws_secretsmanager_secret.app.arn
      },
      {
        Effect = "Allow", Action = ["s3:ListBucket"], Resource = aws_s3_bucket.media.arn
      },
      {
        Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject"], Resource = "${aws_s3_bucket.media.arn}/*"
      },
      {
        Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*"
      },
      {
        Effect = "Allow", Action = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"], Resource = [aws_ecr_repository.app.arn, aws_ecr_repository.web.arn]
      },
      {
        Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.app.arn}:*"
      }
    ]
  })

}
resource "aws_iam_instance_profile" "app" {
  name = var.name
  role = aws_iam_role.ec2.name
}
resource "aws_instance" "app" {

  ami                         = data.aws_ssm_parameter.ami.value
  instance_type               = "t3.small"
  subnet_id                   = var.app_subnet_id
  vpc_security_group_ids      = [aws_security_group.app.id]
  iam_instance_profile        = aws_iam_instance_profile.app.name
  associate_public_ip_address = false
  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }
  root_block_device {
    encrypted   = true
    volume_size = 30
  }
  user_data = "#!/bin/bash\nset -eu\ndnf install -y docker\nsystemctl enable --now docker\ninstall -d -m 700 /opt/anjaneya\n"
  tags = {
    Name = var.name
  }

}
resource "aws_lb" "store" {

  name                       = var.name
  load_balancer_type         = "application"
  internal                   = false
  security_groups            = [aws_security_group.alb.id]
  subnets                    = var.public_subnet_ids
  enable_deletion_protection = true

}
resource "aws_lb_target_group" "store" {

  name     = var.name
  port     = 80
  protocol = "HTTP"
  vpc_id   = var.vpc_id
  health_check {
    path    = "/"
    matcher = "200"
  }

}
resource "aws_lb_target_group_attachment" "app" {
  target_group_arn = aws_lb_target_group.store.arn
  target_id        = aws_instance.app.id
  port             = 80
}
resource "aws_lb_listener" "https" {

  load_balancer_arn = aws_lb.store.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.origin_certificate_arn
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.store.arn
  }

}
resource "aws_route53_record" "origin" {

  zone_id = var.hosted_zone_id
  name    = var.origin_domain
  type    = "A"
  alias {
    name                   = aws_lb.store.dns_name
    zone_id                = aws_lb.store.zone_id
    evaluate_target_health = true
  }

}
resource "aws_cloudfront_distribution" "store" {

  enabled     = true
  aliases     = [var.domain]
  price_class = "PriceClass_200"
  origin {

    domain_name = var.origin_domain
    origin_id   = "store"
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }

  }
  default_cache_behavior {

    target_origin_id         = "store"
    viewer_protocol_policy   = "redirect-to-https"
    allowed_methods          = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods           = ["GET", "HEAD"]
    cache_policy_id          = data.aws_cloudfront_cache_policy.disabled.id
    origin_request_policy_id = data.aws_cloudfront_origin_request_policy.viewer.id
    compress                 = true

  }
  ordered_cache_behavior {

    path_pattern           = "/assets/*"
    target_origin_id       = "store"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = data.aws_cloudfront_cache_policy.assets.id
    compress               = true

  }
  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
  viewer_certificate {
    acm_certificate_arn      = var.cloudfront_certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

}
resource "aws_route53_record" "store" {

  zone_id = var.hosted_zone_id
  name    = var.domain
  type    = "A"
  alias {
    name                   = aws_cloudfront_distribution.store.domain_name
    zone_id                = aws_cloudfront_distribution.store.hosted_zone_id
    evaluate_target_health = false
  }

}
resource "aws_sns_topic" "alarms" {
  name = "${var.name}-alarms"
}
resource "aws_sns_topic_subscription" "alarms" {
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}
resource "aws_cloudwatch_metric_alarm" "errors" {

  alarm_name  = "${var.name}-http-5xx"
  namespace   = "AWS/ApplicationELB"
  metric_name = "HTTPCode_Target_5XX_Count"
  dimensions = {
    LoadBalancer = aws_lb.store.arn_suffix
  }
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 2
  threshold           = 5
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]

}
resource "aws_cloudwatch_metric_alarm" "instance" {

  alarm_name  = "${var.name}-instance-health"
  namespace   = "AWS/EC2"
  metric_name = "StatusCheckFailed"
  dimensions = {
    InstanceId = aws_instance.app.id
  }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 2
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  alarm_actions       = [aws_sns_topic.alarms.arn]

}
output "url" {
  value = "https://${var.domain}"
}
output "instance_id" {
  value = aws_instance.app.id
}
output "database_endpoint" {
  value = aws_db_instance.store.address
}
output "media_bucket" {
  value = aws_s3_bucket.media.id
}
output "application_secret_arn" {
  value = aws_secretsmanager_secret.app.arn
}
output "backend_repository" {
  value = aws_ecr_repository.app.repository_url
}
output "frontend_repository" {
  value = aws_ecr_repository.web.repository_url
}
