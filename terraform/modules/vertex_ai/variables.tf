variable "project" {
  type = string
}

variable "region" {
  type = string
}

variable "endpoint_display_name" {
  type = string
}

variable "endpoint_name" {
  type    = string
  default = "tastetester-vertex-endpoint"
}

variable "bucket_name" {
  type = string
}
