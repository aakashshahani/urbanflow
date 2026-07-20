output "warehouse_bucket" {
  value       = aws_s3_bucket.lakehouse.bucket
  description = "Set WAREHOUSE_BUCKET to this for the AWS target"
}

output "glue_database" {
  value       = aws_glue_catalog_database.urbanflow.name
  description = "Set GLUE_DATABASE to this"
}

output "athena_workgroup" {
  value       = aws_athena_workgroup.urbanflow.name
  description = "Set ATHENA_WORKGROUP to this"
}

output "athena_output_s3" {
  value       = "s3://${aws_s3_bucket.lakehouse.bucket}/athena-results/"
  description = "Set ATHENA_OUTPUT_S3 to this"
}
