# UrbanFlow AWS footprint, deliberately minimal and serverless.
# NO VPC / NAT gateway, NO Redshift, NO MWAA. Everything here is pay-per-use or free-tier,
# so a full teardown (`terraform destroy`) returns cost to ~$0.

# ── Lakehouse bucket: warehouse data + Athena query results ──────────────────
resource "aws_s3_bucket" "lakehouse" {
  bucket        = var.bucket_name
  force_destroy = true # portfolio project: allow clean `terraform destroy`
}

resource "aws_s3_bucket_public_access_block" "lakehouse" {
  bucket                  = aws_s3_bucket.lakehouse.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Expire Athena query results so stray objects never accrue storage cost.
resource "aws_s3_bucket_lifecycle_configuration" "results_expiry" {
  bucket = aws_s3_bucket.lakehouse.id
  rule {
    id     = "expire-athena-results"
    status = "Enabled"
    filter { prefix = "athena-results/" }
    expiration { days = 7 }
  }
}

# ── Glue Data Catalog: the Iceberg catalog for Athena ────────────────────────
resource "aws_glue_catalog_database" "urbanflow" {
  name = var.glue_database
}

# ── Athena workgroup: cap bytes scanned so a runaway query can't blow the budget ─
resource "aws_athena_workgroup" "urbanflow" {
  name          = "urbanflow"
  force_destroy = true

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true
    # Hard stop at 1 GB scanned per query (~$0.005), a guardrail, tune as needed.
    bytes_scanned_cutoff_per_query = 1073741824

    result_configuration {
      output_location = "s3://${aws_s3_bucket.lakehouse.bucket}/athena-results/"
    }
  }
}
