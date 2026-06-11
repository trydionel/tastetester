output "streamlit_firewall" {
  value = google_compute_firewall.streamlit_public.name
}
