module "networking" {
  source               = "./modules/networking"
  project              = var.project
  region               = var.region
  network_name         = var.network_name
  subnetwork_name      = var.subnetwork_name
  subnetwork_ip_cidr_range = var.subnetwork_ip_cidr_range
}

module "vertex_ai" {
  source               = "./modules/vertex_ai"
  project              = var.project
  region               = var.region
  endpoint_display_name = var.endpoint_display_name
  bucket_name          = var.training_bucket_name
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
  streamlit_port       = var.streamlit_port
  allowed_ssh_cidr     = var.allowed_ssh_cidr
  repo_url             = var.repo_url
}

module "streamlit" {
  source               = "./modules/streamlit"
  network              = module.networking.network_self_link
  instance_tag         = module.compute.instance_tag
  streamlit_port       = var.streamlit_port
  allowed_sources      = var.streamlit_allowed_sources
}

module "training_bucket" {
  source                     = "./modules/training_bucket"
  project                    = var.project
  region                     = var.region
  bucket_name                = var.training_bucket_name
  vm_service_account_email   = module.compute.service_account_email
  vertex_service_account_email = module.vertex_ai.service_account_email
  training_script_gcs_path   = var.training_script_gcs_path
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
}
