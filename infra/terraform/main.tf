# Dev environment: one EC2 instance running the stack with Docker Compose.
# Changes from the original: no SSH (access through SSM Session Manager), latest
# Amazon Linux 2023 AMI instead of a hardcoded one, IMDSv2 only, encrypted disk,
# DB passwords generated and stored as SSM SecureStrings instead of in git.

data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

data "aws_vpc" "default" {
  default = true
}

resource "random_password" "db_root" {
  length  = 24
  special = false
}

resource "random_password" "db_app" {
  length  = 24
  special = false
}

resource "aws_ssm_parameter" "db_root" {
  name  = "/bookstore/mysql_root_password"
  type  = "SecureString"
  value = random_password.db_root.result
}

resource "aws_ssm_parameter" "db_app" {
  name  = "/bookstore/mysql_password"
  type  = "SecureString"
  value = random_password.db_app.result
}

# Optional: set the real key later with
#   aws ssm put-parameter --name /bookstore/anthropic_api_key --type SecureString --overwrite --value sk-...
resource "aws_ssm_parameter" "anthropic_key" {
  name  = "/bookstore/anthropic_api_key"
  type  = "SecureString"
  value = "unset"
  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_iam_role" "instance" {
  name = "bookstore-instance"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "read_params" {
  name = "read-bookstore-params"
  role = aws_iam_role.instance.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ssm:GetParameter", "ssm:GetParameters"]
      Resource = [aws_ssm_parameter.db_root.arn, aws_ssm_parameter.db_app.arn, aws_ssm_parameter.anthropic_key.arn]
    }]
  })
}

resource "aws_iam_instance_profile" "instance" {
  name = "bookstore-instance"
  role = aws_iam_role.instance.name
}

resource "aws_security_group" "api" {
  name        = "bookstore-api"
  description = "HTTP to the bookstore API only; no SSH"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = var.allowed_http_cidrs
  }

  egress {
    description = "HTTPS out only: image pulls, package updates, SSM and the Claude API"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "api" {
  ami                    = data.aws_ssm_parameter.al2023.value
  instance_type          = var.instance_type
  iam_instance_profile   = aws_iam_instance_profile.instance.name
  vpc_security_group_ids = [aws_security_group.api.id]
  ebs_optimized          = true
  monitoring             = true

  metadata_options {
    http_tokens   = "required"
    http_endpoint = "enabled"
  }

  root_block_device {
    encrypted   = true
    volume_size = 20
    volume_type = "gp3"
  }

  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    region       = var.region
    api_image    = var.api_image
    compose_file = file("${path.module}/../../docker-compose.yml")
    p_db_root    = aws_ssm_parameter.db_root.name
    p_db_app     = aws_ssm_parameter.db_app.name
    p_anthropic  = aws_ssm_parameter.anthropic_key.name
  })
  user_data_replace_on_change = true

  tags = { Name = "Web Server of Bookstore" }
}
