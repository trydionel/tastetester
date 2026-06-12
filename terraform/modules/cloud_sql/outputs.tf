locals  {
  private_ip = try(google_sql_database_instance.postgres.ip_address[0].ip_address, "")
}

output "connection_name" {
  value = google_sql_database_instance.postgres.connection_name
}

output "private_ip" {
  value = local.private_ip
}

output "connection_string" {
  value = "postgresql+asyncpg://${google_sql_user.db_user.name}:${google_sql_user.db_user.password}@${local.private_ip}:5432/${google_sql_database.db.name}?host=/cloudsql/${google_sql_database_instance.postgres.connection_name}"
}