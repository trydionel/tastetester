resource "google_sql_database_instance" "postgres" {
  provider = google-beta
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
    backup_configuration {
      enabled = true
    }
    activation_policy = "ALWAYS"
  }
}

resource "google_sql_user" "db_user" {
  provider   = google-beta
  project    = var.project
  name       = var.db_user
  instance   = google_sql_database_instance.postgres.name
  password   = var.db_password
}

resource "google_sql_database" "db" {
  provider = google-beta
  project  = var.project
  name     = var.db_name
  instance = google_sql_database_instance.postgres.name
}
