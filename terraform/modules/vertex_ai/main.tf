resource "google_service_account" "vertex_ai" {
  account_id   = "tastetester-vertex-sa"
  display_name = "Tastetester Vertex AI service account"
}

resource "google_vertex_ai_endpoint" "model_endpoint" {
  name         = var.endpoint_name
  display_name = var.endpoint_display_name
  location     = var.region
}

