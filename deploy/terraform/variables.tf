variable "project_id" {
  description = "ID projektu GCP."
  type        = string
}

variable "region" {
  description = "Region (np. us-central1 — free tier e2-micro)."
  type        = string
}

variable "zone" {
  description = "Strefa VM (np. us-central1-a)."
  type        = string
}

variable "domain" {
  description = "Publiczna nazwa hosta aplikacji (Caddy wystawi na nią TLS)."
  type        = string
}

variable "allowed_emails" {
  description = "Lista e-maili dopuszczonych do logowania (FIT_KRASNAL_ALLOWED_EMAILS). Tylko do outputu/dokumentacji — trafia do /etc/fit-krasnal/env ręcznie."
  type        = list(string)
}

variable "name" {
  description = "Prefiks nazw zasobów."
  type        = string
  default     = "fit-krasnal"
}

variable "static_ip_name" {
  description = "Nazwa istniejącego/tworzonego adresu statycznego (regionalnego)."
  type        = string
  default     = "fit-krasnal-ip"
}

variable "machine_type" {
  type    = string
  default = "e2-micro"
}

variable "disk_size_gb" {
  type    = number
  default = 30
}

variable "image" {
  type    = string
  default = "debian-cloud/debian-12"
}

variable "network" {
  description = "Sieć VPC (domyślnie default)."
  type        = string
  default     = "default"
}

variable "vertex_location" {
  description = "Region Vertex AI (FIT_KRASNAL_VERTEX_LOCATION) — tylko do outputu."
  type        = string
  default     = "europe-west1"
}

variable "iap_ssh_range" {
  description = "Zakres źródłowy tuneli IAP TCP (stały, publikowany przez Google)."
  type        = string
  default     = "35.235.240.0/20"
}
