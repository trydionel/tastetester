variable "network" {
  type = string
}

variable "instance_tag" {
  type = string
}

variable "streamlit_port" {
  type = number
}

variable "allowed_sources" {
  type = list(string)
}
