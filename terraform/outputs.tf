output "s3_input_bucket" {
  description = "S3 bucket for input files"
  value       = aws_s3_bucket.input_files.bucket
}

output "s3_processed_bucket" {
  description = "S3 bucket for processed data"
  value       = aws_s3_bucket.processed_data.bucket
}

output "s3_q_tables_bucket" {
  description = "S3 bucket for Q-tables"
  value       = aws_s3_bucket.q_tables.bucket
}

output "lambda_execution_role_arn" {
  description = "Lambda execution role ARN"
  value       = aws_iam_role.lambda_execution_role.arn
}

output "step_functions_arn" {
  description = "Step Functions state machine ARN"
  value       = aws_sfn_state_machine.agentic_workflow.arn
}

output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}

output "account_id" {
  description = "AWS account ID"
  value       = local.account_id
}
