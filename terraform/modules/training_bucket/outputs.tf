output "bucket_name" {
  value = google_storage_bucket.training.name
}

output "training_script_gcs_uri" {
  value = "gs://${google_storage_bucket.training.name}/${google_storage_bucket_object.training_script.name}"
}
