# 🔗 Sơ Đồ Liên Kết Code Chi Tiết

## 📂 Cấu Trúc Thư Mục Code

```
dev_portal_ci_cd_devpos_repoa_to_repob/
├── main.py                           # ⭐ Entry point - Orchestrator
├── config.py                         # ⚙️ Configuration constants
│
├── k8s_generator.py                  # 📦 Generate K8s manifests
│   └── K8sManifestsGenerator class
│       ├── generate_namespace()
│       ├── generate_deployment()
│       ├── generate_service()
│       ├── generate_ingress()
│       ├── generate_pvc()
│       ├── generate_hpa()
│       ├── generate_kustomization()
│       ├── generate_argocd_application()
│       ├── generate_applicationset()
│       └── generate_all()
│
├── github_manager.py                 # 🐙 GitHub API operations
│   └── GitHubManager class
│       ├── create_repository()
│       ├── create_or_update_file()
│       ├── push_files_batch()
│       ├── push_file_to_repo()
│       ├── create_webhook()
│       ├── add_repository_secret()
│       ├── update_repository_b_manifests()
│       └── verify_repository_b_updated()
│
├── framework_templates.py            # 🎨 Dockerfile & CI/CD templates
│   └── FrameworkTemplates class (static methods)
│       ├── get_dockerfile()
│       └── get_cicd_workflow()
│
├── mongodb_client.py                 # 🗄️ MongoDB operations
│   └── MongoDBClient class
│       ├── connect()
│       ├── store_yaml_manifests()
│       ├── get_yaml_manifests()
│       ├── store_application()
│       └── get_application_by_name()
│
├── argocd_service.py                 # ⚡ ArgoCD operations
│   └── ArgoCDService class
│       ├── get_application_status()
│       ├── trigger_sync()
│       ├── create_application()
│       └── wait_for_sync_completion()
│
├── webhook_handler_v2.py             # 🔗 Webhook handler
│   └── GitHubWebhookHandler class
│
├── auto_sync_service.py              # 🔄 Auto sync service
│   └── AutoSyncService class
│
├── deployment_status_monitor.py      # 📊 Deployment monitor
│   └── DeploymentStatusMonitor class
│
├── static/
│   ├── index.html                    # 🖥️ UI Form
│   └── dashboard.html                # 📊 Dashboard
│
└── README.md
```

---

## 🔄 Luồng Liên Kết Code (Flowchart)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    🖥️ FORM UI (index.html)                                  │
│  User nhập:                                                                  │
│  - GitHub Token                                                              │
│  - Repo URL (Repository A)                                                   │
│  - Service Name                                                              │
│  - Framework (django/flask/fastapi/nodejs/etc)                              │
│  - Port, Replicas, Resources                                                 │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │ POST /api/simple-deploy
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ⭐ MAIN.PY (Line 1504-1814)                              │
│                                                                              │
│  @app.post("/api/simple-deploy")                                            │
│  async def simple_deploy(config: SimpleDeployConfig):                       │
│      """🚀 ULTRA SIMPLE: Token + Repo URL → Auto Deploy"""                  │
│                                                                              │
│      # ────────────────────────────────────────────────────────────────       │
│      # STEP 1: Generate K8s Manifests                                       │
│      # ────────────────────────────────────────────────────────────────       │
│      from k8s_generator import K8sManifestsGenerator                         │
│      from config import get_repo_b_url                                     │
│                                                                              │
│      k8s_generator = K8sManifestsGenerator(                                 │
│          app_name=service_name,                                             │
│          namespace=service_name,                                             │
│          docker_image=docker_image,                                          │
│          repo_b_url=repo_b_url,  # ← from config.py                        │
│          project_module_name=service_name.replace('-', '_'),                │
│          framework=config.framework,                                         │
│          main_command=config.main_command,                                   │
│          port=config.port                                                    │
│      )                                                                       │
│      manifests = k8s_generator.generate_all()  # ← Returns Dict[str, str]   │
│                                   │                                          │
│                                   ▼                                          │
│      # Output manifests:                                                     │
│      #   - namespace.yaml                                                    │
│      #   - deployment.yaml                                                   │
│      #   - service.yaml                                                      │
│      #   - ingress.yaml                                                      │
│      #   - pvc.yaml                                                          │
│      #   - hpa.yaml                                                          │
│      #   - kustomization.yaml                                                │
│      #   - argocd-application.yaml                                           │
│      #   - applicationset.yaml                                               │
│                                                                              │
│      # ────────────────────────────────────────────────────────────────       │
│      # STEP 2: Store in MongoDB                                             │
│      # ────────────────────────────────────────────────────────────────       │
│      from mongodb_client import get_mongodb_client                           │
│                                                                              │
│      mongodb = await get_mongodb_client()                                    │
│      git_info = {                                                            │
│          "repo_a_url": config.repo_url,                                     │
│          "repo_a_name": repo_name,                                          │
│          "repo_b_url": repo_b_url,                                          │
│          "last_commit": "latest",                                           │
│          "last_updated": datetime.utcnow().isoformat()                      │
│      }                                                                       │
│      await mongodb.store_yaml_manifests(                                     │
│          app_name=service_name,                                             │
│          manifests=manifests,  # ← from K8sManifestsGenerator              │
│          git_info=git_info                                                  │
│      )                                                                       │
│                                   │                                          │
│                                   ▼                                          │
│      # Stored in MongoDB collection: yaml_manifests                         │
│                                                                              │
│      # ────────────────────────────────────────────────────────────────       │
│      # STEP 3: Push Manifests to Repository B                               │
│      # ────────────────────────────────────────────────────────────────       │
│      from github_manager import GitHubManager                                │
│      from config import get_repo_b_token, get_repo_b_owner                  │
│                                                                              │
│      repo_b_manager = GitHubManager(                                         │
│          github_token=repo_b_token,  # ← from config.py                    │
│          username=repo_b_owner  # ← from config.py                          │
│      )                                                                       │
│                                                                              │
│      # Push từng file vào apps/{service_name}/                              │
│      for filename, content in manifests.items():                             │
│          if filename == 'argocd-application.yaml':                           │
│              continue  # Skip                                                │
│                                                                              │
│          file_path = f"apps/{service_name}/{filename}"                      │
│          await asyncio.to_thread(                                            │
│              repo_b_manager.push_file_to_repo,                              │
│              repo_b_url,  # ← from config.py                                │
│              file_path,                                                      │
│              content,  # ← from manifests dict                              │
│              f"Add {service_name} manifests",                                │
│              "main"                                                          │
│          )                                                                   │
│                                   │                                          │
│                                   ▼                                          │
│      # Files pushed to Repository B:                                        │
│      #   - apps/{service_name}/namespace.yaml                                │
│      #   - apps/{service_name}/deployment.yaml                               │
│      #   - apps/{service_name}/service.yaml                                  │
│      #   - apps/{service_name}/ingress.yaml                                  │
│      #   - apps/{service_name}/pvc.yaml                                      │
│      #   - apps/{service_name}/hpa.yaml                                      │
│      #   - apps/{service_name}/kustomization.yaml                            │
│      #   - k8s/applicationset.yaml (first time only)                         │
│                                                                              │
│      # ────────────────────────────────────────────────────────────────       │
│      # STEP 4: Generate Dockerfile & CI/CD Workflow                         │
│      # ────────────────────────────────────────────────────────────────       │
│      from framework_templates import FrameworkTemplates                      │
│                                                                              │
│      dockerfile_content = FrameworkTemplates.get_dockerfile(                 │
│          framework=config.framework,                                         │
│          main_command=config.main_command,                                   │
│          port=config.port                                                    │
│      )  # ← Returns Dockerfile string                                       │
│                                                                              │
│      cicd_workflow = FrameworkTemplates.get_cicd_workflow(                   │
│          framework=config.framework,                                         │
│          docker_image=docker_image,                                          │
│          service_name=service_name                                           │
│      )  # ← Returns CI/CD workflow YAML string                              │
│                                   │                                          │
│                                   ▼                                          │
│      # Generated files:                                                     │
│      #   - Dockerfile (framework-specific)                                   │
│      #   - .github/workflows/ci-cd.yml (GitHub Actions workflow)            │
│                                                                              │
│      # ────────────────────────────────────────────────────────────────       │
│      # STEP 5: Push Dockerfile & CI/CD to Repository A                      │
│      # ────────────────────────────────────────────────────────────────       │
│      gh_manager = GitHubManager(                                             │
│          github_token=config.github_token,  # ← from user input             │
│          username=github_username  # ← extracted from repo_url              │
│      )                                                                       │
│                                                                              │
│      # Push Dockerfile                                                      │
│      await asyncio.to_thread(                                                │
│          gh_manager.push_file_to_repo,                                      │
│          config.repo_url,  # ← Repository A URL                             │
│          "Dockerfile",                                                       │
│          dockerfile_content,  # ← from FrameworkTemplates                  │
│          f"Add Dockerfile for {config.framework}",                           │
│          "main"                                                              │
│      )                                                                       │
│                                                                              │
│      # Push CI/CD workflow                                                  │
│      await asyncio.to_thread(                                                │
│          gh_manager.push_file_to_repo,                                      │
│          config.repo_url,                                                    │
│          ".github/workflows/ci-cd.yml",                                      │
│          cicd_workflow,  # ← from FrameworkTemplates                       │
│          f"Add CI/CD pipeline for {config.framework}",                       │
│          "main"                                                              │
│      )                                                                       │
│                                   │                                          │
│                                   ▼                                          │
│      # Files pushed to Repository A:                                        │
│      #   - Dockerfile                                                        │
│      #   - .github/workflows/ci-cd.yml                                       │
│      #   - .devportal/service-info.json (metadata backup)                   │
│                                                                              │
│      # ────────────────────────────────────────────────────────────────       │
│      # STEP 6: Add Secrets to Repository A                                  │
│      # ────────────────────────────────────────────────────────────────       │
│      from config import get_repo_b_token                                    │
│                                                                              │
│      # Add REPO_B_TOKEN secret for GitHub Actions to write to Repo B        │
│      await asyncio.to_thread(                                                │
│          gh_manager.add_repository_secret,                                  │
│          repo_name=repo_name,                                               │
│          secret_name="REPO_B_TOKEN",                                        │
│          secret_value=get_repo_b_token()  # ← from config.py               │
│      )                                                                       │
│                                   │                                          │
│                                   ▼                                          │
│      # Secret added to Repository A:                                        │
│      #   - REPO_B_TOKEN (for GitHub Actions)                                │
│                                                                              │
│      # ────────────────────────────────────────────────────────────────       │
│      # STEP 7: Setup Webhook for Repository A                               │
│      # ────────────────────────────────────────────────────────────────       │
│      webhook_url = os.getenv("DEV_PORTAL_WEBHOOK_URL", "")                  │
│      webhook_secret = os.getenv("WEBHOOK_SECRET", None)                     │
│                                                                              │
│      if webhook_url:                                                         │
│          await asyncio.to_thread(                                            │
│              gh_manager.create_webhook,                                     │
│              repo_name=repo_name,                                           │
│              webhook_url=webhook_url,                                        │
│              webhook_secret=webhook_secret,                                  │
│              events=["push", "pull_request"]                                 │
│          )                                                                   │
│                                   │                                          │
│                                   ▼                                          │
│      # Webhook created at:                                                  │
│      #   - Repository A → Dev Portal webhook endpoint                      │
│                                                                              │
│      # Return success response                                              │
│      return {                                                                │
│          "status": "success",                                                │
│          "service_name": service_name,                                       │
│          "repository_a_url": config.repo_url,                               │
│          "repository_b_url": repo_b_url,                                    │
│          ...                                                                 │
│      }                                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼ (Nhánh riêng: GitHub Actions)
┌─────────────────────────────────────────────────────────────────────────────┐
│                    🔄 GITHUB ACTIONS (Repository A)                         │
│                                                                              │
│  File: .github/workflows/ci-cd.yml                                          │
│  [Generated by FrameworkTemplates.get_cicd_workflow()]                      │
│                                                                              │
│  Trigger: on push to main branch                                            │
│                                                                              │
│  Jobs:                                                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 1. test                                                              │  │
│  │    - Checkout code                                                   │  │
│  │    - Set up Python/Node.js/etc.                                      │  │
│  │    - Install dependencies                                            │  │
│  │    - Run tests                                                       │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 2. build-and-deploy (needs: test)                                    │  │
│  │    - Checkout code                                                   │  │
│  │    - Set up Docker Buildx                                            │  │
│  │    - Login to GHCR                                                   │  │
│  │    - Build Docker image                                              │  │
│  │      * Image: ghcr.io/{username}/{repo}:{sha}                        │  │
│  │    - Push to GHCR                                                    │  │
│  │    - Checkout Repository B                                           │  │
│  │      * token: ${{ secrets.REPO_B_TOKEN }}                            │  │
│  │    - Update deployment.yaml                                          │  │
│  │      * Path: apps/{service_name}/deployment.yaml                     │  │
│  │      * Update: image tag to {sha}                                    │  │
│  │    - Commit & Push to Repository B                                   │  │
│  │      * Message: "[skip ci] Update image to {sha}"                   │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼ (Commit to Repository B)
┌─────────────────────────────────────────────────────────────────────────────┐
│                    📦 REPOSITORY B (Updated)                                │
│                                                                              │
│  apps/                                                                       │
│  └── {service_name}/                                                         │
│      ├── namespace.yaml       [✓ từ K8sManifestsGenerator]                  │
│      ├── deployment.yaml      [🔄 UPDATED bởi GitHub Actions]               │
│      │   spec:                                                               │
│      │     containers:                                                       │
│      │     - name: {service_name}                                           │
│      │       image: ghcr.io/{username}/{repo}:{NEW_SHA}  ← UPDATED          │
│      ├── service.yaml         [✓ từ K8sManifestsGenerator]                  │
│      ├── ingress.yaml         [✓ từ K8sManifestsGenerator]                  │
│      ├── pvc.yaml             [✓ từ K8sManifestsGenerator]                  │
│      ├── hpa.yaml             [✓ từ K8sManifestsGenerator]                  │
│      └── kustomization.yaml   [✓ từ K8sManifestsGenerator]                  │
│                                                                              │
│  k8s/                                                                        │
│  └── applicationset.yaml    [✓ từ K8sManifestsGenerator - ONE TIME]         │
│      spec:                                                                   │
│        generators:                                                           │
│        - git:                                                                │
│            repoURL: {REPO_B_URL}                                             │
│            directories:                                                      │
│            - path: apps/*                                                    │
│            refreshSeconds: 30  # Scan mỗi 30s                                │
│        template:                                                             │
│          metadata:                                                           │
│            name: "${{path.basename}}-app"                                    │
│          spec:                                                               │
│            source:                                                           │
│              path: "${{path}}"  # apps/{service_name}                       │
│            destination:                                                       │
│              namespace: "${{path.basename}}"  # {service_name}              │
└─────────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼ (ApplicationSet auto-detects)
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ⚡ ARGOCD (ApplicationSet)                                │
│                                                                              │
│  ApplicationSet "django-apps":                                               │
│  - Scans Repository B every 30 seconds                                       │
│  - Detects new folders in apps/                                              │
│  - Auto-creates Application for each folder                                  │
│                                                                              │
│  When detects change in apps/{service_name}/deployment.yaml:                │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 1. Read updated deployment.yaml                                       │  │
│  │ 2. Detect new image tag                                               │  │
│  │ 3. Trigger sync for {service_name}-app                               │  │
│  │ 4. Apply manifests to Kubernetes                                      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼ (Sync & Deploy)
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ☸️ KUBERNETES                                            │
│                                                                              │
│  Resources deployed:                                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ Namespace: {service_name}                                            │  │
│  │                                                                       │  │
│  │ Deployment: {service_name}                                           │  │
│  │   - Replicas: 2                                                      │  │
│  │   - Image: ghcr.io/{username}/{repo}:{NEW_SHA}                       │  │
│  │   - Pods: {service_name}-xxx-1, {service_name}-xxx-2                 │  │
│  │                                                                       │  │
│  │ Service: {service_name}-service                                      │  │
│  │   - Type: ClusterIP                                                  │  │
│  │   - Port: {port}                                                     │  │
│  │                                                                       │  │
│  │ Ingress: {service_name}-ingress                                      │  │
│  │   - Host: {domain}                                                   │  │
│  │   - TLS: Enabled                                                     │  │
│  │                                                                       │  │
│  │ PVC: {service_name}-pvc                                              │  │
│  │   - Storage: 1Gi                                                     │  │
│  │                                                                       │  │
│  │ HPA: {service_name}-hpa                                              │  │
│  │   - Min: 1                                                           │  │
│  │   - Max: 5                                                           │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔗 Dependency Graph

```
main.py (Entry Point)
│
├─→ config.py (Configuration)
│   ├─ REPO_B_URL
│   ├─ REPO_B_TOKEN
│   ├─ REPO_B_OWNER
│   ├─ REPO_B_NAME
│   ├─ ARGOCD_SERVER_URL
│   ├─ ARGOCD_TOKEN
│   └─ MONGODB_URI
│
├─→ k8s_generator.py (Generate K8s Manifests)
│   └─ K8sManifestsGenerator
│       ├─ generate_namespace() ────┐
│       ├─ generate_deployment() ───┤
│       ├─ generate_service() ──────┤
│       ├─ generate_ingress() ──────┤
│       ├─ generate_pvc() ──────────┤
│       ├─ generate_hpa() ──────────┤
│       ├─ generate_kustomization()─┤
│       ├─ generate_applicationset()┤
│       └─ generate_all() ──────────┴────→ Returns Dict[str, str]
│
├─→ mongodb_client.py (Data Storage)
│   └─ MongoDBClient
│       ├─ connect()
│       ├─ store_yaml_manifests()
│       │   └─ Input: manifests (from K8sManifestsGenerator)
│       └─ get_yaml_manifests()
│
├─→ github_manager.py (GitHub API)
│   └─ GitHubManager
│       ├─ create_repository()
│       ├─ create_or_update_file()
│       ├─ push_files_batch()
│       ├─ push_file_to_repo()
│       │   ├─ Input: repo_url, file_path, content
│       │   └─ Uses GitHub API: PUT /repos/{owner}/{repo}/contents/{path}
│       ├─ create_webhook()
│       │   └─ Uses GitHub API: POST /repos/{owner}/{repo}/hooks
│       └─ add_repository_secret()
│           └─ Uses GitHub API: PUT /repos/{owner}/{repo}/actions/secrets/{name}
│
├─→ framework_templates.py (Templates)
│   └─ FrameworkTemplates (static methods)
│       ├─ get_dockerfile()
│       │   └─ Input: framework, main_command, port
│       │   └─ Returns: Dockerfile string
│       └─ get_cicd_workflow()
│           ├─ Input: framework, docker_image, service_name
│           ├─ Uses config.py: REPO_B_URL, REPO_B_OWNER, REPO_B_NAME
│           └─ Returns: CI/CD workflow YAML string
│
├─→ argocd_service.py (ArgoCD API)
│   └─ ArgoCDService
│       ├─ get_session_token()
│       ├─ get_application_status()
│       ├─ trigger_sync()
│       ├─ create_application()
│       └─ wait_for_sync_completion()
│
└─→ Other Services
    ├─ webhook_handler_v2.py
    ├─ auto_sync_service.py
    ├─ deployment_status_monitor.py
    └─ ...
```

---

## 📊 Data Flow Chi Tiết

### 1. Input Data (User Form)
```json
{
  "github_token": "ghp_xxxxx",
  "repo_url": "https://github.com/username/my-app",
  "service_name": "my-app",
  "framework": "django",
  "main_command": "manage.py",
  "port": 8000,
  "replicas": 2
}
```

### 2. Generated K8s Manifests (k8s_generator.py)
```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: my-app

# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: my-app
spec:
  replicas: 2
  template:
    spec:
      containers:
      - name: my-app
        image: ghcr.io/username/my-app:latest
        ...
```

### 3. Generated Dockerfile (framework_templates.py)
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

### 4. Generated CI/CD Workflow (framework_templates.py)
```yaml
name: CI/CD Pipeline
on:
  push:
    branches: [ main ]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      ...
  build-and-deploy:
    needs: test
    steps:
      - uses: docker/build-push-action@v4
        with:
          tags: ghcr.io/username/my-app:${{ github.sha }}
      - run: |
          sed -i "s|image: ghcr.io/username/my-app:.*|image: ghcr.io/username/my-app:${{ github.sha }}|g" \
            apps/my-app/deployment.yaml
```

### 5. MongoDB Document (mongodb_client.py)
```json
{
  "_id": "...",
  "app_name": "my-app",
  "manifests": {
    "namespace.yaml": "...",
    "deployment.yaml": "...",
    "service.yaml": "...",
    ...
  },
  "git_info": {
    "repo_a_url": "https://github.com/username/my-app",
    "repo_a_name": "my-app",
    "repo_b_url": "https://github.com/quanmbl4255142/repository_b_ci_cd_fpt_repob_devops",
    "last_commit": "latest",
    "last_updated": "2024-01-15T10:30:00Z"
  },
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

### 6. GitHub Actions Updated deployment.yaml
```yaml
# Before (Repository B)
spec:
  containers:
  - name: my-app
    image: ghcr.io/username/my-app:latest

# After (Updated by GitHub Actions)
spec:
  containers:
  - name: my-app
    image: ghcr.io/username/my-app:a1b2c3d4  # ← New SHA
```

### 7. ArgoCD Application (Auto-created by ApplicationSet)
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app-app
  namespace: argocd
spec:
  source:
    repoURL: https://github.com/quanmbl4255142/repository_b_ci_cd_fpt_repob_devops
    path: apps/my-app
  destination:
    server: https://kubernetes.default.svc
    namespace: my-app
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

---

## 🎯 Điểm Liên Kết Quan Trọng

### 1. Configuration Injection
- **config.py** → được import bởi:
  - main.py
  - framework_templates.py
  - github_manager.py (indirect)

### 2. K8s Manifests Flow
- **K8sManifestsGenerator.generate_all()** → 
  - Output: Dict[str, str]
  - Used by: MongoDBClient.store_yaml_manifests()
  - Used by: GitHubManager.push_file_to_repo() → Repository B

### 3. Dockerfile & CI/CD Flow
- **FrameworkTemplates.get_dockerfile()** → 
  - Output: String
  - Used by: GitHubManager.push_file_to_repo() → Repository A/Dockerfile
  
- **FrameworkTemplates.get_cicd_workflow()** → 
  - Output: String (YAML)
  - Used by: GitHubManager.push_file_to_repo() → Repository A/.github/workflows/ci-cd.yml
  - **Template variables**:
    - `{IMAGE_NAME}` → docker_image
    - `{SERVICE_NAME}` → service_name
    - `{REPO_B_OWNER}` → from config.py
    - `{REPO_B_NAME}` → from config.py

### 4. GitHub Operations
- **GitHubManager** được khởi tạo với:
  - **For Repo A**: User's token, user's username
  - **For Repo B**: REPO_B_TOKEN, REPO_B_OWNER (from config.py)

### 5. Secret Management
- **GitHubManager.add_repository_secret()** thêm:
  - `REPO_B_TOKEN` vào Repository A
  - GitHub Actions sử dụng secret này để write vào Repository B

### 6. ApplicationSet Detection
- **applicationset.yaml** được tạo trong k8s/ folder của Repository B
- Quét directories trong apps/ mỗi 30 giây
- Auto-tạo Application cho mỗi folder mới

---

## 🔍 Tìm Code Nhanh

### "Tôi muốn thay đổi cách generate Dockerfile"
→ `framework_templates.py` → `FrameworkTemplates.get_dockerfile()`

### "Tôi muốn thay đổi CI/CD workflow"
→ `framework_templates.py` → `FrameworkTemplates.get_cicd_workflow()`

### "Tôi muốn thay đổi deployment.yaml template"
→ `k8s_generator.py` → `K8sManifestsGenerator.generate_deployment()`

### "Tôi muốn thay đổi cách push lên GitHub"
→ `github_manager.py` → `GitHubManager.push_file_to_repo()` hoặc `push_files_batch()`

### "Tôi muốn thay đổi configuration"
→ `config.py`

### "Tôi muốn thay đổi logic xử lý request"
→ `main.py` → `simple_deploy()` (line 1504)

### "Tôi muốn thay đổi cách lưu MongoDB"
→ `mongodb_client.py` → `MongoDBClient.store_yaml_manifests()`

---

Đây là sơ đồ liên kết code chi tiết nhất của hệ thống Dev Portal CI/CD! 🎉

