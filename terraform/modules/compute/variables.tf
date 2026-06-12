variable "project" {
  type = string
}

variable "region" {
  type = string
}

variable "zone" {
  type = string
}

variable "instance_name" {
  type = string
}

variable "machine_type" {
  type = string
}

variable "boot_disk_size_gb" {
  type = number
}

variable "subnetwork" {
  type = string
}

variable "streamlit_port" {
  type = number
}

variable "streamlit_allowed_sources" {
  type = list(string)
}

variable "prefect_port" {
  type = number
}

variable "prefect_allowed_sources" {
  type = list(string)
}

variable "prefect_basic_auth_username" {
  type = string
}

variable "prefect_basic_auth_password" {
  type = string
  sensitive = true
}

variable "allowed_ssh_cidr" {
  type = string
}

variable "repo_url" {
  type = string
}

variable "network" {
  type = string
}

variable "instance_tag" {
  type = string
  default = "tastetester-vm"
}

variable "postgres_connection_string" {
  type = string
}