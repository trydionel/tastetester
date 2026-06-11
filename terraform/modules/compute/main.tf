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
      image = "ubuntu-os-cloud/ubuntu-24-04-lts"
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

  metadata_startup_script = <<-EOT
    #!/bin/bash
    set -euo pipefail

    apt-get update
    apt-get install -y git python3 python3-venv python3-pip curl

    cd /opt
    rm -rf tastetester
    git clone "${var.repo_url}" tastetester
    cd tastetester

    python3 -m venv /opt/tastetester-venv
    /opt/tastetester-venv/bin/pip install --upgrade pip
    /opt/tastetester-venv/bin/pip install -e .

    cat <<'EOF' > /etc/systemd/system/streamlit.service
    [Unit]
    Description=Streamlit app for tastetester
    After=network.target

    [Service]
    Type=simple
    User=root
    WorkingDirectory=/opt/tastetester
    ExecStart=/opt/tastetester-venv/bin/streamlit run /opt/tastetester/streamlit_app.py --server.port=${var.streamlit_port} --server.address=0.0.0.0
    Restart=always
    RestartSec=10
    Environment=PYTHONUNBUFFERED=1
    Environment=PATH=/opt/tastetester-venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
    EOF

    cat <<'EOF' > /etc/systemd/system/prefect-server.service
    [Unit]
    Description=Prefect server for tastetester
    After=network.target

    [Service]
    Type=simple
    User=root
    WorkingDirectory=/opt/tastetester
    ExecStart=/opt/tastetester-venv/bin/prefect server start --host 0.0.0.0
    Restart=always
    RestartSec=10
    Environment=PYTHONUNBUFFERED=1
    Environment=PATH=/opt/tastetester-venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
    EOF

    systemctl daemon-reload
    systemctl enable streamlit.service
    systemctl enable prefect-server.service
    systemctl start streamlit.service
    systemctl start prefect-server.service
  EOT
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
