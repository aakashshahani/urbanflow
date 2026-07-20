variable "region" {
  description = "AWS region (keep everything in one region to avoid transfer costs)"
  type        = string
  default     = "us-east-1"
}

variable "bucket_name" {
  description = "Globally-unique S3 bucket for the lakehouse warehouse"
  type        = string
  default     = "urbanflow-lakehouse"
}

variable "glue_database" {
  description = "Glue Data Catalog database name"
  type        = string
  default     = "urbanflow"
}
