terraform {
  required_version = ">= 1.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
  # Stan trzymaj POZA repo (domyślnie: local backend, plik wskazany przy init):
  #   terraform init -backend-config="path=$HOME/bilans-kcal-infra/terraform.tfstate"
  backend "local" {}
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}
