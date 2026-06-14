resource "google_project_service" "servicenetworking" {
  project = var.project
  service = "servicenetworking.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "compute" {
  project = var.project
  service = "compute.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "sqladmin" {
  project = var.project
  service = "sqladmin.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "aiplatform" {
  project = var.project
  service = "aiplatform.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "storage" {
  project = var.project
  service = "storage.googleapis.com"
  disable_on_destroy = false
}

module "networking" {
  source               = "./modules/networking"
  project              = var.project
  region               = var.region
  network_name         = var.network_name
  subnetwork_name      = var.subnetwork_name
  subnetwork_ip_cidr_range = var.subnetwork_ip_cidr_range
  depends_on           = [google_project_service.servicenetworking]
}

module "vertex_ai" {
  source               = "./modules/vertex_ai"
  project              = var.project
  region               = var.region
  endpoint_display_name = var.endpoint_display_name
  bucket_name          = var.training_bucket_name
  depends_on           = [google_project_service.aiplatform]
}

module "compute" {
  source               = "./modules/compute"
  project              = var.project
  region               = var.region
  zone                 = var.zone
  instance_name        = var.instance_name
  machine_type         = var.instance_machine_type
  boot_disk_size_gb    = var.boot_disk_size_gb
  network              = module.networking.network_self_link
  subnetwork           = module.networking.subnetwork_self_link
  streamlit_port            = var.streamlit_port
  streamlit_allowed_sources = var.streamlit_allowed_sources
  prefect_port              = var.prefect_port
  prefect_allowed_sources   = var.prefect_allowed_sources
  allowed_ssh_cidr          = var.allowed_ssh_cidr
  prefect_basic_auth_username = var.prefect_basic_auth_username
  prefect_basic_auth_password = var.prefect_basic_auth_password
  repo_url                  = var.repo_url
  postgres_connection_string = module.cloud_sql.connection_string
}

module "training_bucket" {
  source                     = "./modules/training_bucket"
  project                    = var.project
  region                     = var.region
  bucket_name                = var.training_bucket_name
  vm_service_account_email   = module.compute.service_account_email
  vertex_service_account_email = module.vertex_ai.service_account_email
  training_script_gcs_path   = var.training_script_gcs_path
  depends_on                 = [google_project_service.storage]
}

module "cloud_sql" {
  source   = "./modules/cloud_sql"
  project  = var.project
  region   = var.region
  tier     = var.db_tier
  db_name  = var.db_name
  db_user  = var.db_user
  db_password = var.db_password
  network  = module.networking.network_self_link
  depends_on = [
    google_project_service.servicenetworking,
    google_project_service.sqladmin,
    module.networking,
  ]
}

module "prefect" {
  source = "./modules/prefect"
  training_bucket = module.training_bucket.bucket_name
  depends_on = [
    module.compute,
    module.training_bucket
  ]
}