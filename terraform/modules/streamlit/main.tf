resource "google_compute_firewall" "streamlit_public" {
  name    = "allow-streamlit-http"
  network = var.network

  allow {
    protocol = "tcp"
    ports    = ["${var.streamlit_port}"]
  }

  source_ranges = var.allowed_sources
  target_tags   = [var.instance_tag]
}
