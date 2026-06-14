variable "project" {
  type = string
}

variable "region" {
  type = string
}

variable "tier" {
  type = string
}

variable "account_email" {
  type = string
}

variable "db_name" {
  type = string
}

variable "db_user" {
  type = string
}

variable "db_password" {
  type = string
  sensitive = true
}

variable "network" {
  type = string
}
