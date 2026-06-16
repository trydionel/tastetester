resource "google_service_account" "vertex_ai" {
  account_id   = "tastetester-vertex-sa"
  display_name = "Tastetester Vertex AI service account"
}

resource "google_vertex_ai_endpoint" "model_endpoint" {
  name         = var.endpoint_name
  display_name = var.endpoint_display_name
  location     = var.region
}

resource "archive_file" "model_package" {
  type = "tar.gz"
  source_dir = "${path.root}/../models/play_count"
  output_path = "${path.module}/play_count.tgz"
}

resource "google_storage_bucket_iam_member" "vertex_writer" {
  bucket = var.bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.vertex_ai.email}"
}
resource "google_storage_bucket_object" "training_package" {
  name   = var.training_package_gcs_path
  bucket = var.bucket_name
  content = file(archive_file.model_package.output_path)
}