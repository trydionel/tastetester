# OpenTofu deployment for tastetester

Use this folder to provision GCP resources with OpenTofu.

## Quickstart

1. Install OpenTofu: https://opentofu.org
2. Change into this folder:

   cd terraform
3. Initialize providers:

   opentofu init
4. Review the plan:

   opentofu plan
5. Apply the deployment:

   opentofu apply

## Notes

- The compute VM launches a Prefect server and Streamlit service.
- Cloud SQL is configured with private IP-only access.
- Vertex AI resources are provisioned for model endpoint and training artifacts.
