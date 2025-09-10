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

output "s3_customer_graphs_bucket" {
  description = "S3 bucket for customer graph storage"
  value       = aws_s3_bucket.customer_graphs.bucket
}

output "neptune_cluster_endpoint" {
  description = "Neptune cluster endpoint"
  value       = aws_neptune_cluster.customer_graphs.endpoint
}

output "neptune_cluster_reader_endpoint" {
  description = "Neptune cluster reader endpoint"
  value       = aws_neptune_cluster.customer_graphs.reader_endpoint
}

output "neptune_cluster_id" {
  description = "Neptune cluster identifier"
  value       = aws_neptune_cluster.customer_graphs.cluster_identifier
}

output "graph_extraction_lambda_role_arn" {
  description = "Graph extraction lambda execution role ARN"
  value       = aws_iam_role.graph_extraction_lambda.arn
}

output "neptune_persistence_lambda_role_arn" {
  description = "Neptune persistence lambda execution role ARN"
  value       = aws_iam_role.neptune_persistence_lambda.arn
}

output "customer_graphs_kms_key_id" {
  description = "KMS key ID for customer graphs encryption"
  value       = aws_kms_key.customer_graphs.key_id
}

output "lambda_neptune_security_group_id" {
  description = "Security group ID for Lambda to access Neptune"
  value       = aws_security_group.lambda_neptune_access.id
}
