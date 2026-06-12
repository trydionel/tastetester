resource "google_compute_health_check" "streamlit" {
  name               = "tastetester-streamlit-health-check"
  check_interval_sec = 5
  timeout_sec        = 5
  healthy_threshold  = 2
  unhealthy_threshold = 2

  http_health_check {
    port        = var.streamlit_port
    request_path = "/streamlit/"
  }
}

resource "google_compute_health_check" "prefect" {
  name               = "tastetester-prefect-health-check"
  check_interval_sec = 5
  timeout_sec        = 5
  healthy_threshold  = 2
  unhealthy_threshold = 2

  http_health_check {
    port        = var.prefect_port
    request_path = "/prefect/api/"
  }
}

resource "google_compute_backend_service" "streamlit" {
  name                  = "tastetester-streamlit-backend"
  protocol              = "HTTP"
  port_name             = "streamlit"
  timeout_sec           = 30
  connection_draining_timeout_sec = 0

  backend {
    group = var.instance_group
  }

  health_checks = [google_compute_health_check.streamlit.self_link]
}

resource "google_compute_backend_service" "prefect" {
  name                  = "tastetester-prefect-backend"
  protocol              = "HTTP"
  port_name             = "prefect"
  timeout_sec           = 30
  connection_draining_timeout_sec = 0

  backend {
    group = var.instance_group
  }

  health_checks = [google_compute_health_check.prefect.self_link]
}

resource "google_compute_url_map" "app" {
  name = "tastetester-url-map"

  default_service = google_compute_backend_service.streamlit.self_link

  host_rule {
    hosts = ["*"]
    path_matcher = "path-matcher"
  }

  path_matcher {
    name            = "path-matcher"
    default_service = google_compute_backend_service.streamlit.self_link

    path_rule {
      paths   = ["/streamlit/*"]
      service = google_compute_backend_service.streamlit.self_link
    }

    path_rule {
      paths   = ["/prefect/*"]
      service = google_compute_backend_service.prefect.self_link
    }
  }
}

resource "google_compute_target_http_proxy" "http_proxy" {
  name   = "tastetester-http-proxy"
  url_map = google_compute_url_map.app.self_link
}

resource "google_compute_global_forwarding_rule" "http_forwarding_rule" {
  name       = "tastetester-http-forwarding-rule"
  ip_address = var.lb_ip_address
  ip_protocol = "TCP"
  port_range = "80"
  target     = google_compute_target_http_proxy.http_proxy.self_link
}
