output "endpoint_name" {
  value = google_vertex_ai_endpoint.model_endpoint.name
}

output "service_account_email" {
  value = google_service_account.vertex_ai.email
}
