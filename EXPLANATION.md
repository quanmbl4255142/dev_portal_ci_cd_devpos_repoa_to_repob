# 📚 GIẢI THÍCH TOÀN BỘ DỰ ÁN DEV PORTAL CI/CD

## 🎯 TỔNG QUAN HỆ THỐNG

Dự án này là một **Dev Portal tự động hóa CI/CD** cho phép deploy các ứng dụng (Django, Flask, FastAPI, Node.js, Spring Boot, Go, .NET) lên Kubernetes thông qua ArgoCD mà không cần cấu hình thủ công.

---

## 🔄 KIẾN TRÚC TỔNG QUAN

```
User Input (Form) 
    ↓
Dev Portal (FastAPI)
    ↓
├─ Generate K8s Manifests → Push vào Repository B
├─ Generate Dockerfile + CI/CD → Push vào Repository A  
├─ Create ArgoCD Application
    ↓
GitHub Actions (Repository A)
    ↓
├─ Build Docker Image → Push GHCR
├─ Update Repository B (deployment.yaml với image mới)
    ↓
ArgoCD ApplicationSet
    ↓
├─ Detect changes trong Repository B
├─ Auto-sync & Deploy lên Kubernetes
```

---

## 📁 CẤU TRÚC FILE VÀ LOGIC

### 1. **`config.py`** - Cấu hình tập trung

**Mục đích:** Lưu trữ tất cả các biến cấu hình quan trọng

**Nội dung chính:**
- `REPO_B_URL`: URL của Repository B (nơi lưu K8s manifests)
- `REPO_B_TOKEN`: GitHub token để push vào Repo B
- `ARGOCD_SERVER_URL`: URL của ArgoCD server
- `MONGODB_URI`: Connection string cho MongoDB
- `AUTO_SYNC_INTERVAL`: Thời gian tự động sync từ ArgoCD (30s)

**Cách hoạt động:**
- Đọc từ environment variables, fallback về giá trị mặc định
- Cung cấp helper functions để lấy config

**Kết nối với:**
- Tất cả các file khác import config từ đây
- `main.py` sử dụng để truyền config vào các service

---

### 2. **`main.py`** - API Server & Orchestration

**Mục đích:** FastAPI server, điều phối toàn bộ quy trình deploy

**Các endpoint chính:**

#### `POST /api/simple-deploy`
- Nhận config từ user (token, repo URL, framework, service name)
- Quy trình:
  1. Tạo K8s manifests (`k8s_generator.py`)
  2. Lưu vào MongoDB (`mongodb_client.py`)
  3. Push manifests vào Repository B (`github_manager.py`)
  4. Tạo Dockerfile + CI/CD workflow (`framework_templates.py`)
  5. Push vào Repository A (`github_manager.py`)
  6. Tạo ArgoCD Application (`argocd_app_creator.py`)

#### `POST /api/webhook/github`
- Nhận webhook từ GitHub khi có push
- Xử lý bởi `github_webhook_handler.py`

#### `GET /api/dashboard/applications`
- Lấy danh sách applications từ MongoDB

**Kết nối với:**
- **Tất cả các module khác** - Orchestrate toàn bộ flow

---

### 3. **`start.py`** - Entry Point

**Mục đích:** Khởi động Dev Portal và auto-sync service

**Logic:**
```python
1. Start auto_sync_service (background task)
2. Start FastAPI server (port 8090)
3. Graceful shutdown khi nhận KeyboardInterrupt
```

**Kết nối với:**
- `main.py`: Import và chạy FastAPI app
- `auto_sync_service.py`: Start background sync

---

### 4. **`github_manager.py`** - GitHub Operations

**Mục đích:** Quản lý tất cả thao tác với GitHub API

**Các chức năng chính:**

#### `push_files()` - Push nhiều files
- Sử dụng Git Tree API để push nhiều files trong 1 commit
- Fallback về individual push nếu batch fail
- Đặc biệt xử lý `.github/workflows/` files

#### `update_repository_b_manifests()` - Update Repo B
- Push manifests vào `apps/{app_name}/` directory
- Structure: 
  ```
  apps/
    app-1/
      deployment.yaml
      service.yaml
      ...
    app-2/
      ...
  ```

#### `create_or_update_file()` - Update 1 file
- Check file tồn tại (GET với SHA)
- Update hoặc create mới

#### `add_repository_secret()` - Add GitHub Actions secrets
- Encrypt secret bằng PyNaCl
- Thêm vào repository secrets (REPO_B_TOKEN, etc.)

**Kết nối với:**
- `main.py`: Gọi khi cần push code/manifests
- `framework_templates.py`: Push Dockerfile + CI/CD
- `k8s_generator.py`: Push K8s manifests

---

### 5. **`k8s_generator.py`** - Generate K8s Manifests

**Mục đích:** Tạo tất cả file YAML cần thiết cho K8s deployment

**Các manifests được generate:**

#### `generate_namespace()` - Namespace YAML
- Tạo namespace riêng cho mỗi app

#### `generate_deployment()` - Deployment YAML
- **Quan trọng:** Có ArgoCD Image Updater annotations:
  ```yaml
  annotations:
    argocd-image-updater.argoproj.io/image-list: app=ghcr.io/user/repo
    argocd-image-updater.argoproj.io/write-back-method: git
    argocd-image-updater.argoproj.io/write-back-target: apps/{app}/deployment.yaml
  ```
- Init containers, resources, probes, volumes

#### `generate_service()` - Service YAML
- ClusterIP service expose port

#### `generate_ingress()` - Ingress YAML
- Nginx ingress với TLS

#### `generate_hpa()` - Horizontal Pod Autoscaler
- Auto-scale dựa trên CPU/Memory

#### `generate_applicationset()` - ApplicationSet YAML
- **Quan trọng:** ArgoCD ApplicationSet tự động detect apps mới
- Scan `apps/*` directories trong Repository B
- Tự tạo Application cho mỗi app

#### `generate_all()` - Generate tất cả
- Trả về dict với tất cả manifests
- Structure: `{'namespace.yaml': content, 'deployment.yaml': content, ...}`

**Kết nối với:**
- `main.py`: Gọi `generate_all()` khi deploy
- `github_manager.py`: Push manifests vào Repo B
- `mongodb_client.py`: Lưu manifests vào MongoDB

---

### 6. **`framework_templates.py`** - Framework Templates

**Mục đích:** Generate Dockerfile và CI/CD workflow cho từng framework

**Hỗ trợ frameworks:**
- Django, Flask, FastAPI (Python)
- Node.js
- Spring Boot (Java)
- Go
- .NET

**Các functions:**

#### `get_dockerfile(framework, main_command, port)`
- Trả về Dockerfile template phù hợp với framework
- Multi-stage build cho Spring Boot, Go, .NET

#### `get_cicd_workflow(framework, docker_image, service_name)`
- Generate GitHub Actions workflow:
  1. **Test job**: Chạy tests (pytest, npm test, mvn test, ...)
  2. **Build job**:
     - Build Docker image
     - Push lên GHCR với tag là commit SHA
     - Checkout Repository B
     - Update `deployment.yaml` với image mới
     - Commit + Push Repo B với `[skip ci]`

**Workflow quan trọng:**
```yaml
- name: Update deployment image
  run: |
    # Tìm deployment.yaml trong apps/{service_name}/
    sed -i "s|image: ${IMAGE_PATTERN}:.*|image: ${IMAGE_PATTERN}:${SHA}|g" \
      apps/${SERVICE_NAME}/deployment.yaml
```

**Kết nối với:**
- `main.py`: Generate Dockerfile + CI/CD khi deploy
- `github_manager.py`: Push vào Repository A

---

### 7. **`argocd_app_creator.py`** - ArgoCD Application Creator

**Mục đích:** Tạo ArgoCD Application khi có app mới

**Các methods:**

#### `create_application_via_api()`
- Gọi ArgoCD REST API để tạo Application
- URL: `POST /api/v1/applications`
- Payload:
  ```json
  {
    "metadata": {"name": "app-name", "namespace": "argocd"},
    "spec": {
      "source": {
        "repoURL": "https://github.com/.../repo-b",
        "path": "apps/app-name"
      },
      "destination": {
        "server": "https://kubernetes.default.svc",
        "namespace": "app-name"
      },
      "syncPolicy": {
        "automated": {"prune": true, "selfHeal": true}
      }
    }
  }
  ```

#### `check_if_exists()`
- Check Application đã tồn tại chưa
- Nếu có → update, nếu không → create

#### `generate_application_yaml()`
- Generate YAML để apply bằng kubectl (fallback)

**Kết nối với:**
- `main.py`: Tạo Application sau khi push manifests
- `argocd_service.py`: Sử dụng để tương tác ArgoCD API

---

### 8. **`github_webhook_handler.py`** - Webhook Handler

**Mục đích:** Xử lý webhook từ GitHub để trigger ArgoCD sync

**Các events xử lý:**

#### `handle_push_event()` - Push Event
Phân biệt 2 loại repository:

1. **Repository B** (K8s manifests):
   - Detect thay đổi trong `apps/` folder
   - Refresh ApplicationSet
   - Trigger sync cho từng app thay đổi
   - Start monitoring deployment

2. **Repository A** (Source code):
   - Detect code changes (.py, .js, .go, ...)
   - Tìm app_name từ MongoDB (dựa vào repo_url)
   - **Đợi 90s** cho GitHub Actions build xong
   - Trigger ArgoCD sync
   - Start monitoring deployment

**Flow xử lý Repo A:**
```
Push code → Webhook received
    ↓
Find app_name from MongoDB
    ↓
Wait 90s (GitHub Actions build image + update Repo B)
    ↓
Trigger ArgoCD sync
    ↓
Monitor deployment status
```

#### `verify_webhook_signature()`
- Verify SHA256/SHA1 signature từ GitHub
- Security: Prevent unauthorized webhooks

**Kết nối với:**
- `main.py`: Register endpoint `/api/webhook/github`
- `deployment_status_monitor.py`: Monitor sau khi sync
- `mongodb_client.py`: Tìm app_name từ repo_url

---

### 9. **`mongodb_client.py`** - MongoDB Client

**Mục đích:** Quản lý database operations

**2 Collections:**

#### `applications` - ArgoCD Applications Data
- Sync từ ArgoCD qua `argo_data_fetcher.py`
- Fields: name, namespace, healthStatus, syncStatus, gitRepo, deployments, services

#### `yaml_manifests` - YAML Manifests Storage
- Lưu K8s manifests được generate
- Fields: app_name, yaml_manifests (dict), git_info, argocd_info, status
- **Quan trọng:** Index trên `git_info.repo_a_url` để tìm app nhanh

**Các operations:**

#### `store_yaml_manifests()`
- Lưu manifests khi deploy mới
- Upsert (insert or update)

#### `find_app_name_by_repo_url()`
- **Quan trọng:** Tìm app_name từ repo_url
- Sử dụng index để query nhanh
- Try nhiều URL variations (.git, trailing slash, http/https)

#### `update_deployment_details()`
- Update status từ ArgoCD
- Replicas, pod status, health status

**Kết nối với:**
- Tất cả các module cần lưu/đọc data
- `github_webhook_handler.py`: Tìm app_name
- `argo_data_fetcher.py`: Lưu ArgoCD data

---

### 10. **`argo_data_fetcher.py`** - ArgoCD Data Fetcher

**Mục đích:** Lấy dữ liệu thật từ ArgoCD API và lưu vào MongoDB

**Các methods:**

#### `get_argocd_applications()`
- GET `/api/v1/applications`
- Lấy danh sách tất cả Applications

#### `transform_argocd_app_to_mongodb()`
- Transform ArgoCD Application format → MongoDB document
- Extract: healthStatus, syncStatus, gitRepo, resources, ...

#### `sync_applications_to_mongodb()`
- Lấy tất cả apps từ ArgoCD
- Transform và upsert vào MongoDB
- **Xóa apps không còn trong ArgoCD** (cleanup)
- Sync deployment details cho từng app

**Kết nối với:**
- `auto_sync_service.py`: Gọi định kỳ để sync
- `mongodb_client.py`: Upsert data

---

### 11. **`auto_sync_service.py`** - Auto Sync Service

**Mục đích:** Tự động sync dữ liệu từ ArgoCD vào MongoDB

**Logic:**
```python
while is_running:
    await sync_if_changed()
    await asyncio.sleep(poll_interval)  # 30s
```

#### `sync_if_changed()`
- Gọi `argo_data_fetcher.py` để sync
- Update `last_sync_time`

**Kết nối với:**
- `start.py`: Start background task khi khởi động
- `argo_data_fetcher.py`: Sync data

---

### 12. **`deployment_status_monitor.py`** - Deployment Monitor

**Mục đích:** Monitor deployment status sau khi ArgoCD sync

**Logic:**

#### `poll_deployment_status()`
```python
while elapsed < timeout:
    status = get_detailed_status(app_name)
    if is_fully_deployed:
        return success
    if health == 'Failed':
        return failed
    await sleep(check_interval)  # 10s
```

#### `get_detailed_status()`
- Get từ ArgoCD API
- Extract: health_status, sync_status, running_pods, total_pods
- Check: `is_fully_deployed = (health == 'Healthy' && sync == 'Synced' && pods running)`

#### `update_mongodb_status()`
- Update status vào MongoDB collection `yaml_manifests`

**Kết nối với:**
- `github_webhook_handler.py`: Monitor sau khi sync
- `mongodb_client.py`: Update status

---

## 🔄 LUỒNG HOẠT ĐỘNG CHI TIẾT

### **LUỒNG DEPLOY MỚI (User Click Deploy)**

```
1. User submit form → POST /api/simple-deploy
   └─> main.py

2. Generate K8s Manifests
   └─> k8s_generator.py::generate_all()
   └─> Returns: {namespace.yaml, deployment.yaml, service.yaml, ...}

3. Store in MongoDB
   └─> mongodb_client.py::store_yaml_manifests()
   └─> Collection: yaml_manifests

4. Push Manifests vào Repository B
   └─> github_manager.py::update_repository_b_manifests()
   └─> Push vào: apps/{service_name}/

5. Generate Dockerfile + CI/CD
   └─> framework_templates.py::get_dockerfile()
   └─> framework_templates.py::get_cicd_workflow()

6. Push vào Repository A
   └─> github_manager.py::push_files()
   └─> Push: Dockerfile, .github/workflows/ci-cd.yml

7. Create ArgoCD Application
   └─> argocd_app_creator.py::create_application_via_api()
   └─> OR: ApplicationSet tự detect apps mới
```

---

### **LUỒNG KHI CÓ CODE MỚI (Push vào Repo A)**

```
1. Developer push code → GitHub
   └─> GitHub webhook trigger

2. Webhook received
   └─> POST /api/webhook/github
   └─> github_webhook_handler.py::handle_push_event()

3. Detect Repository A push
   └─> Find app_name từ MongoDB (by repo_url)
   └─> mongodb_client.py::find_app_name_by_repo_url()

4. Wait 90 seconds
   └─> Đợi GitHub Actions build image + update Repo B

5. GitHub Actions (Repo A)
   ├─> Build Docker image
   ├─> Push GHCR: ghcr.io/user/repo:abc123
   ├─> Checkout Repository B
   ├─> Update: apps/{service_name}/deployment.yaml
   │   └─> image: ghcr.io/user/repo:abc123
   └─> Commit + Push Repo B

6. Webhook từ Repository B (sau khi Actions push)
   └─> github_webhook_handler.py::_handle_repository_b_push()
   └─> Refresh ApplicationSet
   └─> Trigger ArgoCD sync

7. ArgoCD Auto-Deploy
   └─> Detect changes trong Repo B
   └─> Sync Application
   └─> Apply to Kubernetes
   └─> Pods rebuild với image mới

8. Monitor Deployment
   └─> deployment_status_monitor.py::monitor_deployment()
   └─> Poll status mỗi 10s
   └─> Update MongoDB khi done
```

---

### **LUỒNG AUTO SYNC (Background)**

```
1. Start background task
   └─> start.py::start_auto_sync()

2. Loop every 30 seconds
   └─> auto_sync_service.py::sync_if_changed()

3. Fetch từ ArgoCD
   └─> argo_data_fetcher.py::sync_applications_to_mongodb()

4. Update MongoDB
   └─> mongodb_client.py::upsert_application()
   └─> Collection: applications
```

---

## 🔗 KẾT NỐI GIỮA CÁC FILE

### **Dependency Graph**

```
start.py
└─> main.py (FastAPI app)
    ├─> github_manager.py (Push code)
    ├─> k8s_generator.py (Generate manifests)
    ├─> framework_templates.py (Generate Dockerfile/CI-CD)
    ├─> argocd_app_creator.py (Create ArgoCD App)
    ├─> mongodb_client.py (Store data)
    ├─> github_webhook_handler.py (Handle webhooks)
    │   ├─> mongodb_client.py (Find app_name)
    │   └─> deployment_status_monitor.py (Monitor)
    └─> auto_sync_service.py (Background sync)
        └─> argo_data_fetcher.py (Fetch ArgoCD)
            └─> mongodb_client.py (Store)
```

### **Data Flow**

```
User Input → main.py
    ↓
Generate Manifests → k8s_generator.py
    ↓
Store → mongodb_client.py (yaml_manifests collection)
    ↓
Push to GitHub → github_manager.py
    ↓
GitHub Actions → Build & Push Image
    ↓
Update Repo B → github_manager.py
    ↓
Webhook → github_webhook_handler.py
    ↓
ArgoCD Sync → argocd_app_creator.py
    ↓
Kubernetes → Deployment
    ↓
Monitor → deployment_status_monitor.py
    ↓
Update MongoDB → mongodb_client.py
```

### **Config Flow**

```
Environment Variables
    ↓
config.py (centralized)
    ↓
Import vào các modules:
- main.py
- auto_sync_service.py
- github_webhook_handler.py
- argo_data_fetcher.py
```

---

## 🎯 CÁC COMPONENT CHÍNH

### **1. Repository A (Source Code)**
- Chứa source code của ứng dụng
- Có Dockerfile và CI/CD workflow
- GitHub Actions build image khi có push

### **2. Repository B (K8s Manifests)**
- Structure: `apps/{app-name}/`
- Mỗi app có: namespace.yaml, deployment.yaml, service.yaml, ingress.yaml, hpa.yaml
- ApplicationSet scan `apps/*` để tự tạo Applications

### **3. ArgoCD**
- ApplicationSet: Auto-detect apps trong Repo B
- Application: Deploy từng app vào K8s
- Image Updater: Tự động update image khi có tag mới

### **4. MongoDB**
- **applications**: ArgoCD data (sync từ ArgoCD API)
- **yaml_manifests**: Generated manifests và status

### **5. Dev Portal**
- FastAPI server (port 8090)
- Web UI tại `/static/index.html`
- Dashboard tại `/static/dashboard.html`

---

## 📊 CẤU TRÚC DỮ LIỆU

### **MongoDB Collection: yaml_manifests**

```json
{
  "app_name": "django-test-72",
  "yaml_manifests": {
    "namespace.yaml": "...",
    "deployment.yaml": "...",
    "service.yaml": "..."
  },
  "git_info": {
    "repo_a_url": "https://github.com/user/repo-a",
    "repo_a_name": "repo-a",
    "last_commit": "abc123",
    "last_updated": "2024-01-01T00:00:00Z"
  },
  "status": {
    "health_status": "Healthy",
    "sync_status": "Synced",
    "replicas": 2,
    "ready_replicas": 2
  }
}
```

### **MongoDB Collection: applications**

```json
{
  "name": "django-test-72",
  "namespace": "django-test-72",
  "healthStatus": "Healthy",
  "syncStatus": "Synced",
  "gitRepo": {
    "url": "https://github.com/user/repo-b",
    "path": "apps/django-test-72"
  },
  "deployments": [...],
  "services": [...]
}
```

---

## 🔐 SECURITY & CONFIGURATION

### **Environment Variables**

```bash
# Repository B
REPO_B_URL=https://github.com/user/repo-b
REPO_B_TOKEN=ghp_xxx
REPO_B_OWNER=user
REPO_B_NAME=repo-b

# ArgoCD
ARGOCD_SERVER_URL=http://localhost:8081
ARGOCD_TOKEN=xxx (Bearer token)
ARGOCD_ADMIN_PASSWORD=admin123

# MongoDB
MONGODB_URI=mongodb+srv://...
MONGODB_DB=argocd_apps

# Webhook
GITHUB_WEBHOOK_SECRET=xxx (for signature verification)

# Auto Sync
AUTO_SYNC_INTERVAL=30 (seconds)
REPO_A_WEBHOOK_DELAY=90 (seconds - wait for GitHub Actions)
```

---

## 📝 TÓM TẮT

### **Entry Point:**
- `start.py` → Start FastAPI + Auto Sync

### **Orchestration:**
- `main.py` → Điều phối toàn bộ flow

### **Core Services:**
- `github_manager.py` → GitHub operations
- `k8s_generator.py` → Generate manifests
- `framework_templates.py` → Generate Dockerfile/CI-CD
- `argocd_app_creator.py` → Create ArgoCD apps
- `mongodb_client.py` → Database operations

### **Background Services:**
- `auto_sync_service.py` → Sync ArgoCD → MongoDB
- `argo_data_fetcher.py` → Fetch từ ArgoCD API
- `deployment_status_monitor.py` → Monitor deployments

### **Webhook Handler:**
- `github_webhook_handler.py` → Handle GitHub webhooks, trigger sync

### **Configuration:**
- `config.py` → Centralized config

---

## ✅ KẾT LUẬN

Hệ thống hoạt động hoàn toàn tự động:
1. User chỉ cần điền form và click Deploy
2. Dev Portal tự generate tất cả cần thiết
3. GitHub Actions tự build và update
4. ArgoCD tự deploy lên Kubernetes
5. Hệ thống tự monitor và sync status

Tất cả các file kết nối với nhau thông qua:
- **Function calls** (import modules)
- **MongoDB** (shared database)
- **GitHub API** (shared repository)
- **ArgoCD API** (shared ArgoCD server)
- **Configuration** (shared config.py)

