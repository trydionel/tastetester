output "network_self_link" {
  description = "Self-link of the VPC network."
  value       = module.networking.network_self_link
}

output "subnetwork_self_link" {
  description = "Self-link of the subnetwork."
  value       = module.networking.subnetwork_self_link
}

output "compute_instance_name" {
  description = "Name of the deployed compute instance."
  value       = module.compute.instance_name
}

output "compute_external_ip" {
  description = "External IP address of the compute instance."
  value       = module.compute.instance_external_ip
}

output "streamlit_url" {
  description = "Public URL for the Streamlit application."
  value       = "http://${module.compute.instance_external_ip}:${var.streamlit_port}"
}

output "prefect_url" {
  description = "Public URL for the Prefect server."
  value       = "http://${module.compute.instance_external_ip}:${var.prefect_port}"
}

output "training_bucket_name" {
  description = "Name of the training Cloud Storage bucket."
  value       = module.training_bucket.bucket_name
}

output "training_package_gcs_uri" {
  description = "GCS URI for the uploaded Vertex AI training script."
  value       = module.vertex_ai.training_package_gcs_uri
}

output "cloud_sql_connection_name" {
  description = "Connection name for the Cloud SQL instance."
  value       = module.cloud_sql.connection_name
}

output "cloud_sql_private_ip" {
  description = "Private IP address for the Cloud SQL instance."
  value       = module.cloud_sql.private_ip
}

output "vertex_ai_endpoint_id" {
  description = "Full resource name of the Vertex AI endpoint."
  value       = module.vertex_ai.endpoint_id
}

output "vertex_ai_endpoint_uri" {
  description = "Full resource name of the Vertex AI endpoint."
  value       = module.vertex_ai.model_endpoint_uri
}

output "vertex_ai_prediction_uri" {
  description = "Full HTTPS prediction URL for the deployed Vertex AI endpoint."
  value       = module.vertex_ai.prediction_uri
}

output "vertex_ai_service_account_email" {
  description = "Service account email used for Vertex AI operations."
  value       = module.vertex_ai.service_account_email
}
