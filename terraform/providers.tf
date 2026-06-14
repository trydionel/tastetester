terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.36"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 7.36"
    }
    prefect = {
      source = "prefecthq/prefect"
      version = "~> 3.0"
    }
  }
}

provider "google" {
  project = var.project
  region  = var.region
  zone    = var.zone
}

provider "google-beta" {
  project = var.project
  region  = var.region
  zone    = var.zone
}

provider "prefect" {
  profile = "ephemeral"
  endpoint = "http://0.0.0.0:4200"
}
