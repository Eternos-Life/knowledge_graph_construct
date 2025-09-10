variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-west-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "agentic-framework"
}

variable "neptune_instance_class" {
  description = "Neptune instance class"
  type        = string
  default     = "db.t3.medium"
}

variable "neptune_instance_count" {
  description = "Number of Neptune instances"
  type        = number
  default     = 1
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 14
}
