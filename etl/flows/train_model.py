from prefect import flow, task
from prefect_gcp.cloud_storage import GcsBucket
from google.cloud import aiplatform

from etl.common import root_path

TRAIN_VERSION = "xgboost-cpu.1-1"
DEPLOY_VERSION = "xgboost-cpu.1-1"

TRAIN_IMAGE = "gcr.io/cloud-aiplatform/training/{}:latest".format(TRAIN_VERSION)
DEPLOY_IMAGE = "gcr.io/cloud-aiplatform/prediction/{}:latest".format(DEPLOY_VERSION)

TRAIN_COMPUTE="n1-standard-4" 
DEPLOY_COMPUTE="n1-standard-4" 

@task
def upload_artifacts_to_gcs(bucket: GcsBucket):
    return bucket.upload_from_folder(root_path().joinpath('etl', 'artifacts'), 'artifacts')

@task
def initiate_training(package_uri: str, training_data_uri: str, model_output_uri: str):
    job = aiplatform.CustomPythonPackageTrainingJob(
        display_name="tastetester-training",
        python_package_gcs_uri=package_uri,
        python_module_name="trainer.task",
        container_uri=TRAIN_IMAGE
    )

    return job.run(
        replica_count=1,
        machine_type=TRAIN_COMPUTE,
        args=[
            "--train-data-path", training_data_uri,
            "--model-output-path", model_output_uri
        ],
        sync=True
    )

@task
def upload_model_to_gcs(model_path: str):
    return aiplatform.Model.upload(
        display_name="tastetester-model",
        artifact_uri=model_path,
        serving_container_image_uri=DEPLOY_IMAGE,
        sync=True
    )

@task
def deploy_model(model: aiplatform.Model):
    return model.deploy(
        deployed_model_display_name="tastetester-deployed-model",
        machine_type=DEPLOY_COMPUTE,
        sync=True
    )

@flow
def train_model(bucket_name: str, package_uri: str):
    bucket = GcsBucket.load(bucket_name)
    bucket_name = bucket.bucket
    project_id = bucket.gcp_credentials.project
    train_data_uri = "gs://{}/artifacts/tracks.parquet".format(bucket_name)
    model_output_uri = "gs://{}/model".format(bucket_name)

    aiplatform.init(project=project_id, staging_bucket=bucket_name)

    upload_artifacts_to_gcs(bucket)
    initiate_training(package_uri, train_data_uri, model_output_uri)
    model = upload_model_to_gcs(model_output_uri)
    deploy_model(model)