variable "project" {
  type        = string
  description = "The GCP project ID to deploy tastetester into."
}

variable "region" {
  type        = string
  description = "The GCP region to deploy resources into."
  default     = "us-central1"
}

variable "zone" {
  type        = string
  description = "The GCP zone to deploy compute resources into."
  default     = "us-central1-a"
}

variable "account_email" {
  type = string
  description = "The primary email address for the GCP account."
}

variable "network_name" {
  type        = string
  description = "The VPC network name for the deployment."
  default     = "tastetester-network"
}

variable "subnetwork_name" {
  type        = string
  description = "The subnet name for the deployment."
  default     = "tastetester-subnet"
}

variable "subnetwork_ip_cidr_range" {
  type        = string
  description = "CIDR range for the private subnetwork."
  default     = "10.8.0.0/16"
}

variable "training_bucket_name" {
  type        = string
  description = "The Cloud Storage bucket name for training data and artifacts."
  default     = "tastetester-training-bucket"
}

variable "training_script_gcs_path" {
  type        = string
  description = "Object path in the training bucket for the Vertex AI training script."
  default     = "vertex-ai/training/vertex_ai_training.py"
}

variable "instance_name" {
  type        = string
  description = "The Compute Engine instance name."
  default     = "tastetester-vm"
}

variable "instance_machine_type" {
  type        = string
  description = "The machine type for the compute instance."
  default     = "e2-small"
}

variable "boot_disk_size_gb" {
  type        = number
  description = "The boot disk size in GB for the compute instance."
  default     = 50
}

variable "repo_url" {
  type        = string
  description = "Git repository URL used by the startup script to fetch application code."
  default     = "https://github.com/trydionel/tastetester.git"
}

variable "streamlit_port" {
  type        = number
  description = "Port exposed by the Streamlit service."
  default     = 8501
}

variable "streamlit_allowed_sources" {
  type        = list(string)
  description = "CIDR blocks permitted to access the public Streamlit service."
  default     = ["0.0.0.0/0"]
}

variable "prefect_port" {
  type        = number
  description = "Port exposed by the Prefect server."
  default     = 4200
}

variable "prefect_allowed_sources" {
  type        = list(string)
  description = "CIDR blocks permitted to access the public Prefect service."
  default     = ["0.0.0.0/0"]
}

variable "prefect_basic_auth_username" {
  type        = string
  description = "Username for Prefect UI basic authentication."
}

variable "prefect_basic_auth_password" {
  type        = string
  description = "Password for Prefect UI basic authentication."
  sensitive   = true
}

variable "allowed_ssh_cidr" {
  type        = string
  description = "CIDR block permitted to SSH into the compute instance."
  default     = "0.0.0.0/0"
}

variable "db_tier" {
  type        = string
  description = "Cloud SQL instance tier."
  default     = "db-f1-micro"
}

variable "db_name" {
  type        = string
  description = "Database name for the Prefect/Postgres instance."
  default     = "prefect"
}

variable "db_user" {
  type        = string
  description = "Database user for the Cloud SQL instance."
  default     = "prefect"
}

variable "db_password" {
  type        = string
  description = "Password for the Cloud SQL database user."
  default     = "prefect"
  sensitive   = true
}

variable "endpoint_display_name" {
  type        = string
  description = "Vertex AI endpoint display name."
  default     = "tastetester-vertex-endpoint"
}
