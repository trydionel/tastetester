resource "google_service_account" "compute" {
  account_id   = "tastetester-vm-sa"
  display_name = "Tastetester VM service account"
}

resource "google_compute_instance" "vm" {
  name         = var.instance_name
  machine_type = var.machine_type
  zone         = var.zone
  tags         = [var.instance_tag]

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2604-lts-amd64"
      size  = var.boot_disk_size_gb
    }
  }

  network_interface {
    subnetwork = var.subnetwork
    access_config {}
  }

  service_account {
    email  = google_service_account.compute.email
    scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
  }

  metadata = {
    repo_url = var.repo_url
  }

  metadata_startup_script = templatefile("${path.module}/startup.sh", {
    repo_url = var.repo_url,
    prefect_basic_auth_username = var.prefect_basic_auth_username,
    prefect_basic_auth_password = var.prefect_basic_auth_password,
    prefect_port = var.prefect_port,
    streamlit_port = var.streamlit_port,
    postgres_connection_string = var.postgres_connection_string
  })
}

resource "google_compute_firewall" "ssh_access" {
  name    = "allow-ssh"
  network = var.network

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = [var.allowed_ssh_cidr]
  target_tags   = [var.instance_tag]
}

resource "google_compute_firewall" "streamlit_access" {
  name    = "allow-streamlit-http"
  network = var.network

  allow {
    protocol = "tcp"
    ports    = ["${var.streamlit_port}"]
  }

  source_ranges = var.streamlit_allowed_sources
  target_tags   = [var.instance_tag]
}

resource "google_compute_firewall" "prefect_access" {
  name    = "allow-prefect-http"
  network = var.network

  allow {
    protocol = "tcp"
    ports    = ["${var.prefect_port}"]
  }

  source_ranges = var.prefect_allowed_sources
  target_tags   = [var.instance_tag]
}
