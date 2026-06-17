locals {
  external_ip = google_compute_instance.vm.network_interface[0].access_config[0].nat_ip
}

output "instance_name" {
  value = google_compute_instance.vm.name
}

output "instance_external_ip" {
  value = local.external_ip
}

output "instance_tag" {
  value = join(",", google_compute_instance.vm.tags)
}

output "service_account_email" {
  value = google_service_account.compute.email
}

output "prefect_api_url" {
  value = "http://${local.external_ip}:${var.prefect_port}/api"
}
