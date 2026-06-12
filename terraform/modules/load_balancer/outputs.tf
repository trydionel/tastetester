output "load_balancer_address" {
  value = var.lb_ip_address
}

output "load_balancer_url" {
  value = "http://${var.lb_ip_address}"
}
