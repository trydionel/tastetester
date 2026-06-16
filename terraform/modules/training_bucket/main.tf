resource "google_storage_bucket" "training" {
  name                        = var.bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false
}

resource "google_storage_bucket_iam_member" "vm_writer" {
  bucket = google_storage_bucket.training.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${var.vm_service_account_email}"
}

resource "google_storage_bucket_iam_member" "vm_bucket_reader" {
  bucket = google_storage_bucket.training.name
  role   = "roles/storage.legacyBucketReader"
  member = "serviceAccount:${var.vm_service_account_email}"
}