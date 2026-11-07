output "api_url" {
  value = "http://${aws_instance.api.public_dns}"
}

output "ssm_session_command" {
  description = "Shell access without SSH"
  value       = "aws ssm start-session --target ${aws_instance.api.id} --region ${var.region}"
}
