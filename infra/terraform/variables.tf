variable "region" {
  type    = string
  default = "us-east-1"
}

variable "instance_type" {
  type    = string
  default = "t3.small"
}

variable "api_image" {
  description = "Container image built by CI, e.g. ghcr.io/<user>/bookstore-ai-platform:latest"
  type        = string
}

variable "allowed_http_cidrs" {
  description = "Who may reach the API on port 80"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}
