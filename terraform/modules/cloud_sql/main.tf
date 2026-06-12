resource "google_service_account" "cloud_sql" {
  account_id   = "tastetester-sql-sa"
  display_name = "Tastetester SQL service account"
}

resource "google_sql_database_instance" "postgres" {
  provider = google
  project  = var.project
  name             = "tastetester-sql"
  database_version = "POSTGRES_16"
  region           = var.region

  settings {
    tier = var.tier
    ip_configuration {
      ipv4_enabled    = false
      private_network = var.network
    }
    database_flags {
      name  = "cloudsql.iam_authentication"
      value = "on"
    }
    backup_configuration {
      enabled = true
    }
    activation_policy = "ALWAYS"
    data_api_access = "ALLOW_DATA_API"
  }
}

resource "google_sql_user" "db_user" {
  provider   = google
  project    = var.project
  name       = var.db_user
  instance   = google_sql_database_instance.postgres.name
  password   = var.db_password
}

resource "google_sql_database" "db" {
  provider = google
  project  = var.project
  name     = var.db_name
  instance = google_sql_database_instance.postgres.name
}

resource "google_sql_user" "iam_user" {
  name     = "trydionel@gmail.com" # FIXME: Why doesn't this work with the service account email?
  instance = google_sql_database_instance.postgres.name
  type     = "CLOUD_IAM_USER" 
  database_roles = ["cloudsqlsuperuser"]  # Roles granted to the user. Smaller roles are preferred, if exist.
}

resource "google_sql_provision_script" "install_extensions" {
  instance = google_sql_database_instance.postgres.name
  database = google_sql_database.db.name
  script = file("${path.module}/setup.sql")

  depends_on = [google_sql_user.iam_user]
}