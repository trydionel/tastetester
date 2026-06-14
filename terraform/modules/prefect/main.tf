resource "prefect_flow" "flow" {
  provider = prefect
  name         = "tastetester-etl-flow"
  tags         = ["tf-test"]
}

resource "prefect_deployment" "deployment" {
  provider = prefect
  name                     = "tastetester-etl"
  description              = "string"
  flow_id                  = prefect_flow.flow.id
  entrypoint               = "main.py:main"
  tags                     = ["test"]
  path   = "/opt/tastetester"
  paused = false
  pull_steps = [
    {
      type      = "set_working_directory",
      directory = "/opt/tastetester",
    },
    {
      type     = "pull_from_gcs",
      requires = "prefect-gcp>=0.6.0"
      bucket   = var.training_bucket,
      folder   = "listens-data",
    },
    {
      type            = "run_shell_script"
      script          = "mv listens-data/ data/"
      directory       = "/opt/tastetester"
      expand_env_vars = true
      stream_output   = true
    }
  ]
  work_queue_name     = "default"
}