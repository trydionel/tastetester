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

resource "google_storage_bucket_iam_member" "vertex_writer" {
  bucket = google_storage_bucket.training.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${var.vertex_service_account_email}"
}

resource "google_storage_bucket_object" "training_script" {
  name   = var.training_script_gcs_path
  bucket = google_storage_bucket.training.name
  content = <<-EOF
    # Vertex AI training script placeholder.
    from __future__ import annotations
    import argparse
    import json
    import os
    import pandas as pd
    import xgboost as xgb

    def parse_args():
        parser = argparse.ArgumentParser()
        parser.add_argument('--train-data-path', required=True)
        parser.add_argument('--model-output-path', required=True)
        return parser.parse_args()

    def main():
        args = parse_args()

        df = pd.read_parquet(args.train_data_path)
        X = df.drop(columns=['total_plays'])
        y = df['total_plays']

        model = xgb.XGBRegressor(objective='count:poisson', n_estimators=100, max_depth=8)
        model.fit(X, y)

        os.makedirs(os.path.dirname(args.model_output_path), exist_ok=True)
        model.save_model(args.model_output_path)

    if __name__ == '__main__':
        main()
    EOF
}
