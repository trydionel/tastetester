resource "google_service_account" "vertex_ai" {
  account_id   = "tastetester-vertex-sa"
  display_name = "Tastetester Vertex AI service account"
}

resource "google_vertex_ai_endpoint" "model_endpoint" {
  name         = var.endpoint_name
  display_name = var.endpoint_display_name
  location     = var.region
}

resource "google_ml_engine_model" "xgboost_model" {
  name        = "tastetester-xgboost-model"
  description = "XGBoost model placeholder for tastetester"
  project     = var.project
  regions     = [var.region]
}

