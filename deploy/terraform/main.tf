# Fit Krasnal — minimalna, utwardzona infrastruktura na GCP:
# e2-micro (free tier) + Caddy/TLS, 80/443 z internetu, SSH tylko przez IAP,
# konto usługi z dostępem do Vertex AI.
#
# Bootstrap systemu (pakiety, użytkownik, venv, Caddy, sekrety) robi
# deploy/setup-vm.sh, uruchamiany przez SSH/IAP po `terraform apply`
# (patrz output `ssh_command`). Świadomie NIE jako startup-script: skrypt
# generuje sekrety do /etc/fit-krasnal/env i wymaga ręcznego uzupełnienia
# OAuth; przy każdym restarcie VM nie ma potrzeby go powtarzać.

locals {
  apis = [
    "compute.googleapis.com",
    "aiplatform.googleapis.com",
    "iap.googleapis.com",
    "oslogin.googleapis.com",
    "secretmanager.googleapis.com",
    "logging.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each                   = toset(local.apis)
  service                    = each.value
  disable_on_destroy         = false
  disable_dependent_services = false
}

# ── Konto usługi VM: tylko Vertex AI + zapis logów, bez kluczy ──────────
resource "google_service_account" "vm" {
  account_id   = "${var.name}-vm"
  display_name = "Fit Krasnal VM (Vertex AI + logi)"
}

resource "google_project_iam_member" "vm_aiplatform" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.vm.email}"
}

resource "google_project_iam_member" "vm_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.vm.email}"
}

# ── Adres statyczny (regionalny, STANDARD tier — tańszy egress) ─────────
resource "google_compute_address" "ip" {
  name         = var.static_ip_name
  region       = var.region
  address_type = "EXTERNAL"
  network_tier = "STANDARD"

  lifecycle {
    prevent_destroy = true
  }
}

# ── Firewall: 80/443 z internetu, 22 tylko z IAP ────────────────────────
resource "google_compute_firewall" "web" {
  name          = "${var.name}-allow-web"
  network       = var.network
  direction     = "INGRESS"
  source_ranges = ["0.0.0.0/0"]
  target_tags   = [var.name]

  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }
}

resource "google_compute_firewall" "ssh_iap" {
  name          = "${var.name}-allow-ssh-iap"
  network       = var.network
  direction     = "INGRESS"
  source_ranges = [var.iap_ssh_range]
  target_tags   = [var.name]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}

# ── VM ───────────────────────────────────────────────────────────────────
resource "google_compute_instance" "vm" {
  name         = var.name
  machine_type = var.machine_type
  zone         = var.zone
  tags         = [var.name]

  boot_disk {
    initialize_params {
      image = var.image
      size  = var.disk_size_gb
      type  = "pd-standard"
    }
  }

  network_interface {
    network = var.network
    access_config {
      nat_ip       = google_compute_address.ip.address
      network_tier = "STANDARD"
    }
  }

  service_account {
    email  = google_service_account.vm.email
    scopes = ["cloud-platform"]
  }

  metadata = {
    enable-oslogin = "TRUE"
  }

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  allow_stopping_for_update = true

  depends_on = [google_project_service.apis]
}
