terraform {
  required_version = ">= 1.6"
  required_providers {
    aws    = { source = "hashicorp/aws", version = "~> 5.80" }
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }

  # Remote state (recommended). Create the bucket once, then uncomment:
  # backend "s3" {
  #   bucket       = "my-tfstate-bucket"
  #   key          = "bookstore-ai-platform/terraform.tfstate"
  #   region       = "us-east-1"
  #   use_lockfile = true
  # }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { Project = "bookstore-ai-platform", ManagedBy = "terraform" }
  }
}
