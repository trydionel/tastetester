#!/bin/bash
set -euxo pipefail

apt-get update
apt-get install -y git python3 python3-venv python3-pip curl libpq-dev

cd /opt
rm -rf tastetester
git clone --single-branch --branch terraform "${repo_url}" tastetester
cd tastetester

python3 -m venv /opt/tastetester-venv
/opt/tastetester-venv/bin/python -m pip install uv
UV_PROJECT_ENVIRONMENT=/opt/tastetester-venv /opt/tastetester-venv/bin/uv sync --frozen

# Get external IP address from metadata server, as we can't get it at build time from Terraform
EXTERNAL_IP=$(curl -sfH "Metadata-Flavor: Google" "http://169.254.169.254/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip")
    if [ -z "$EXTERNAL_IP" ]; then
      echo "Unable to determine external IP from metadata server"
      exit 1
    fi

# Configure prefect
/opt/tastetester-venv/bin/prefect config set PREFECT_SERVER_API_AUTH_STRING="${prefect_basic_auth_username}:${prefect_basic_auth_password}"
/opt/tastetester-venv/bin/prefect config set PREFECT_API_AUTH_STRING="${prefect_basic_auth_username}:${prefect_basic_auth_password}"
/opt/tastetester-venv/bin/prefect config set PREFECT_API_URL="http://$EXTERNAL_IP:${prefect_port}/api"
/opt/tastetester-venv/bin/prefect config set PREFECT_API_DATABASE_CONNECTION_URL="${postgres_connection_string}"
/opt/tastetester-venv/bin/prefect server database upgrade -y

cat <<'EOF' > /etc/systemd/system/streamlit.service
[Unit]
Description=Streamlit app for tastetester
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/tastetester
ExecStart=/opt/tastetester-venv/bin/streamlit run /opt/tastetester/streamlit_app.py --server.port=${streamlit_port} --server.address=0.0.0.0
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1
Environment=PATH=/opt/tastetester-venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
EOF

cat <<EOF > /etc/systemd/system/prefect-server.service
[Unit]
Description=Prefect server for tastetester
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/tastetester
ExecStart=/opt/tastetester-venv/bin/prefect server start --host 0.0.0.0
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1
Environment=PATH=/opt/tastetester-venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
EOF

cat <<EOF > /etc/systemd/system/prefect-worker.service
[Unit]
Description=Prefect worker for tastetester
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/tastetester
ExecStart=/opt/tastetester-venv/bin/prefect worker start -p "tastetester-work-pool"
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1
Environment=PATH=/opt/tastetester-venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
EOF

systemctl daemon-reload
systemctl enable streamlit.service
systemctl enable prefect-server.service
systemctl enable prefect-worker.service
systemctl start streamlit.service
systemctl start prefect-server.service

# Wait for server to be ready
/opt/tastetester-venv/bin/prefect server status --wait

# Create prefect resources via CLI (idempotent: || true to skip if already exists)
/opt/tastetester-venv/bin/prefect work-pool create "tastetester-work-pool" --type process || true
/opt/tastetester-venv/bin/prefect work-queue create "tastetester-work-queue" --pool "tastetester-work-pool" --limit 1 || true
/opt/tastetester-venv/bin/prefect deploy /opt/tastetester/main.py:main --name "tastetester-etl" --pool "tastetester-work-pool" --work-queue "tastetester-work-queue" || true

systemctl start prefect-worker.service