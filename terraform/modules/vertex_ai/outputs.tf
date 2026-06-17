output "model_id" {
  value = google_vertex_ai_model.play_count.name
}

output "endpoint_id" {
  value = google_vertex_ai_endpoint.model_endpoint.id
}

output "model_endpoint_uri" {
  value = google_vertex_ai_endpoint.model_endpoint.id
}

output "prediction_uri" {
  description = "Full HTTPS prediction URL for the Vertex AI endpoint"
  value       = "https://${var.region}-aiplatform.googleapis.com/v1/${google_vertex_ai_endpoint.model_endpoint.id}:predict"
}

output "service_account_email" {
  value = google_service_account.vertex_ai.email
}

output "training_package_gcs_uri" {
  value = "gs://${var.bucket_name}/${google_storage_bucket_object.training_package.name}"
}
