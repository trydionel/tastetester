## Plan: Terraform Deployment Infrastructure for tastetester

TL;DR: Standardize on GCP and build a low-cost Terraform scaffold for a single Compute Engine instance running Prefect and Streamlit, Cloud SQL, a training data bucket, and Vertex AI training + deployment with prebuilt XGBoost containers. Keep the environment simple, single-zone, and locked down: only Streamlit is publicly accessible.

**Steps**
1. Document the runtime requirements from the repo.
   - Prefect server + worker need a PostgreSQL backend.
   - Streamlit app loads `app.recommender.Recommender`, which should become inference-only and call Vertex AI directly.
   - The current app does not expose a standalone inference API; inference will now use the Vertex AI endpoint.
   - Existing local orchestration is expressed in `docker-compose.yml` with Prefect and PostgreSQL.

2. Define the deployment architecture.
   - Service 1: Single Compute Engine VM for Prefect server, Prefect worker, and Streamlit.
   - Service 2: Cloud SQL PostgreSQL instance for Prefect state and any relational storage.
   - Service 3: GCP Cloud Storage bucket for raw Spotify exports and transformed Parquet training data.
   - Service 4: Vertex AI training jobs and deployed XGBoost model endpoint.

3. Create a Terraform repo layout.
   - `terraform/` root for infrastructure code.
   - `terraform/modules/` for shared GCP modules: `compute`, `cloud_sql`, `streamlit`, `training_bucket`, `vertex_ai`, `networking`.
   - Single environment only — no separate dev/staging/prod folders needed.
   - Shared entrypoints: `main.tf`, `variables.tf`, `providers.tf`, `outputs.tf`, `terraform.tfvars`.

4. Design the GCP deployment.
   - Cloud SQL for PostgreSQL in a single zone with private IP and minimal instance class (for example, `db-f1-micro` or `db-g1-small`), with automatic backups and maintenance windows configured.
   - One Compute Engine VM for Prefect and Streamlit to save cost, using a low-cost `e2-micro`/`e2-small` machine type and a persistent boot disk for VM-local state.
   - Use a persistent disk for the VM so Prefect state and local ETL artifacts survive restarts.
   - Use a Cloud Storage bucket for raw Spotify exports, transformed Parquet datasets, training code uploads, and model artifacts.
   - Use Vertex AI prebuilt XGBoost training containers for both training and inference.
   - Restrict all services to internal networking except Streamlit, which is the only publicly routable service.
   - Use idle shutdown / scheduling for the compute VM where possible, and consider scheduled Cloud SQL start/stop for non-production usage windows.

5. Codify the infrastructure in Terraform.
   - `terraform/modules/compute` should create a `google_compute_instance` with a startup script to install and launch Prefect, Streamlit, and any local tooling.
   - `terraform/modules/compute` should also create a firewall rule allowing HTTP/HTTPS to Streamlit and private access for Prefect worker traffic only.
   - `terraform/modules/cloud_sql` should provision a `google_sql_database_instance` with private IP access, a low-cost instance tier, and managed credentials stored in Terraform outputs or Secret Manager.
   - `terraform/modules/training_bucket` should provision a `google_storage_bucket` with regional storage, uniform bucket-level access, and IAM bindings for the VM and Vertex AI service accounts.
   - `terraform/modules/vertex_ai` should provision the Vertex AI training job template, managed `google_vertex_ai_model`, and `google_vertex_ai_endpoint` resources. It should also define the model artifact path in GCS.
   - `terraform/modules/networking` should handle the VPC, subnetwork, private service access for Cloud SQL, and any IAM bindings needed for Vertex AI.
   - Use top-level `main.tf`, `variables.tf`, `providers.tf`, and `outputs.tf` to wire the modules together and expose values like bucket name, Cloud SQL connection string, and Vertex AI endpoint URI.
   - Add Terraform-driven scheduling for cost control: a `google_compute_resource_policy` schedule or instance metadata for idle shutdown, and optionally a Cloud SQL start/stop schedule for non-production hours.

6. Define the model workflow.
   - The training bucket stores raw Spotify exports, transformed Parquet training files, and the standalone Vertex AI training script.
   - Prefect orchestrates ETL, uploads transformed Parquet data to the bucket, and then kicks off Vertex AI training.
   - Vertex AI uses the prebuilt XGBoost training container and the uploaded training script to train the model.
   - The trained model artifact is saved back into the bucket, then Vertex AI creates or updates a Model resource and deploys it to an endpoint.
   - Streamlit uses the Vertex AI endpoint directly for inference; no separate inference API is required.

6. Address persistence and storage.
   - Use Cloud SQL for persistent relational storage.
   - Use a single persistent disk attached to the VM for Prefect and any local ETL state.
   - Use a Cloud Storage bucket for raw input data, transformed Parquet training data, training code, and model artifacts.
   - Ensure the bucket and Vertex AI service account have the permissions needed to read training data and write model artifacts.
   - Keep the network locked down: Cloud SQL private IP, private access for Vertex AI as appropriate, and only Streamlit exposed publicly.

7. Plan Terraform implementation details.
   - Create `terraform/modules/compute` for the single VM, startup scripts, and firewall rules.
   - Create `terraform/modules/cloud_sql` for PostgreSQL instance provisioning and connection secrets.
   - Create `terraform/modules/streamlit` for configuring the Streamlit service on the VM.
   - Create `terraform/modules/training_bucket` for the Cloud Storage bucket and IAM bindings.
   - Create `terraform/modules/vertex_ai` for Vertex AI training jobs, Model resources, and endpoint deployments.
   - Use variables for region, machine type, disk size, DB credentials, bucket names, training code paths, and service account bindings.

8. Validate and verify.
   - Run `terraform init` and `terraform plan` for the GCP configuration.
   - Verify the architecture can create the single VM, Cloud SQL, training bucket, and Vertex AI resources.
   - Confirm `PREFECT_API_URL`, Cloud SQL connection strings, bucket names, and Vertex AI endpoint details are exposed to runtime configuration.
   - Confirm Streamlit is the only public service and that Prefect and Cloud SQL remain internal.
   - Confirm Prefect can upload transformed Parquet data to GCS and trigger Vertex AI training.

**Relevant files**
- `docker-compose.yml` — existing local service layout and the current Prefect/Postgres pattern.
- `streamlit_app.py` — current frontend entrypoint and direct use of `Recommender`, which will need to become Vertex AI inference-only.
- `app/recommender.py` — model inference path and artifact dependencies.
- `bin/recommend` — example of CLI-based inference via `Recommender`.
- `main.py` — Prefect flow orchestration, showing the need for Prefect backend.

**Decisions**
- Standardize on GCP for deployment.
- Use a single Compute Engine VM for Prefect and Streamlit to minimize cost.
- Use Cloud SQL single-zone for Postgres.
- Use a Cloud Storage bucket for raw exports, transformed Parquet data, training code, and model artifacts.
- Use Vertex AI prebuilt XGBoost training and serving containers.
- Keep Streamlit public, and all other services internal.
- Manage both infrastructure and app/ETL deployment via Terraform in a single environment.
- Keep `Recommender` inference-only and call the Vertex AI endpoint directly.

**Further Considerations**
1. Do you want Streamlit and Prefect on the same VM process, or split them across two inexpensive VMs for a bit more isolation while still keeping costs low? A single VM is simplest.
2. Should the training script be uploaded to GCS by Terraform, or should Prefect copy it from the repo into the bucket at runtime? Both are possible; Terraform-based upload is simpler for an initial deployment.
3. Plan service account permissions carefully so the VM can write to GCS, Cloud SQL is private, and Vertex AI jobs can run securely.
4. Use scheduled or idle shutdown for the VM and Cloud SQL in non-critical hours, and enforce startup windows only when Prefect jobs or Streamlit access are expected.
