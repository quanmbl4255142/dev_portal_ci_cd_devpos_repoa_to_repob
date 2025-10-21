# 🔄 LUỒNG MỚI: MongoDB YAML Sync

## 📋 **TỔNG QUAN**

Luồng mới sử dụng **MongoDB làm trung gian lưu trữ YAML manifests** thay vì Repository_B, với 2 phương án sync:

### **Phương án 1: MongoDB → ArgoCD (Ưu tiên)**
```
Repository_A → Webhook → Dev Portal → MongoDB (YAML) → ArgoCD → Kubernetes
```

### **Phương án 2: MongoDB → Repository_B → ArgoCD (Fallback)**
```
Repository_A → Webhook → Dev Portal → MongoDB (YAML) → Repository_B → ArgoCD → Kubernetes
```

## 🏗️ **KIẾN TRÚC MỚI**

### **Components đã thêm:**

1. **MongoDB YAML Storage** (`mongodb_client.py`)
   - Collection `yaml_manifests` để lưu K8s manifests
   - Methods: `store_yaml_manifests()`, `update_yaml_manifests()`, `get_yaml_manifests()`

2. **ArgoCD MongoDB Sync** (`argocd_mongodb_sync.py`)
   - Sync trực tiếp từ MongoDB → ArgoCD
   - Tạo temporary directory với YAML files
   - Update ArgoCD Application source

3. **Fallback Repository_B Sync** (`fallback_repo_b_sync.py`)
   - Fallback khi ArgoCD sync thất bại
   - Push YAML manifests từ MongoDB → Repository_B
   - Repository_B → ArgoCD (existing flow)

4. **Enhanced Webhook Handler** (`github_webhook_handler.py`)
   - Nhận webhook từ Repository_A
   - Detect code changes và update YAML trong MongoDB
   - Trigger ArgoCD sync ngay lập tức

## 🔄 **LUỒNG HOẠT ĐỘNG**

### **1. Initial Deploy (generate-and-deploy)**
```
User Request → Dev Portal
    ↓
Generate Django Project → Push to Repository_A
    ↓
GitHub Actions → Build Docker Image → Push to GHCR
    ↓
Generate K8s Manifests → Store in MongoDB
    ↓
Try: MongoDB → ArgoCD (Direct)
    ↓ (if fails)
Fallback: MongoDB → Repository_B → ArgoCD
```

### **2. Code Changes (Webhook)**
```
Repository_A Push → GitHub Webhook → Dev Portal
    ↓
Detect Code Changes → Update YAML in MongoDB
    ↓
Try: MongoDB → ArgoCD (Direct)
    ↓ (if fails)
Fallback: MongoDB → Repository_B → ArgoCD
```

## 📊 **MONGODB SCHEMA**

### **Collection: `yaml_manifests`**
```javascript
{
  "_id": "ObjectId",
  "app_name": "django-api",
  "yaml_manifests": {
    "namespace.yaml": "apiVersion: v1\nkind: Namespace\n...",
    "deployment.yaml": "apiVersion: apps/v1\nkind: Deployment\n...",
    "service.yaml": "apiVersion: v1\nkind: Service\n...",
    "pvc.yaml": "apiVersion: v1\nkind: PersistentVolumeClaim\n...",
    "ingress.yaml": "apiVersion: networking.k8s.io/v1\nkind: Ingress\n..."
  },
  "git_info": {
    "repo_a_url": "https://github.com/user/django-api.git",
    "repo_a_name": "django-api",
    "last_commit": "latest",
    "last_updated": "2025-01-27T10:00:00Z"
  },
  "argocd_info": {
    "application_name": "django-api",
    "sync_status": "Synced",
    "last_sync": "2025-01-27T10:05:00Z"
  },
  "version": 1,
  "created_at": "2025-01-27T10:00:00Z",
  "updated_at": "2025-01-27T10:30:00Z"
}
```

## 🚀 **API ENDPOINTS MỚI**

### **YAML Management APIs**
- `GET /api/yaml-manifests` - Get all YAML manifests
- `GET /api/yaml-manifests/{app_name}` - Get specific YAML manifests
- `POST /api/yaml-manifests/{app_name}/sync` - Sync YAML to ArgoCD/Repository_B
- `POST /api/yaml-manifests/sync-all` - Sync all YAML manifests
- `DELETE /api/yaml-manifests/{app_name}` - Delete YAML manifests
- `GET /api/yaml-manifests/{app_name}/status` - Get sync status

### **Webhook APIs**
- `POST /api/webhook/github` - Enhanced GitHub webhook (Repository_A + Repository_B)
- `GET /api/webhook/health` - Webhook health check

### **Webhook Management APIs** (via GitHubManager)
- `create_webhook()` - Tạo webhook cho repository
- `update_webhook()` - Cập nhật webhook
- `get_webhooks()` - Lấy danh sách webhooks
- `delete_webhook()` - Xóa webhook

## ⚙️ **ENVIRONMENT VARIABLES**

### **MongoDB**
```bash
MONGODB_URL=mongodb://localhost:27017
MONGODB_DATABASE=argocd_apps
```

### **ArgoCD**
```bash
ARGOCD_SERVER=https://argocd.example.com
ARGOCD_TOKEN=your-argocd-token
```

### **GitHub**
```bash
GITHUB_TOKEN=your-github-token
REPO_B_URL=https://github.com/user/repository-b.git
```

## 🔧 **CẤU HÌNH WEBHOOK**

### **Auto Webhook Setup**
Khi tạo Repository_A mới, Dev Portal sẽ **tự động setup webhook**:

```bash
# Environment Variables
export DEV_PORTAL_WEBHOOK_URL=https://your-dev-portal.com/api/webhook/github
export GITHUB_WEBHOOK_SECRET=your-webhook-secret
```

### **Repository_A Webhook** (Auto-created)
```
URL: https://your-dev-portal.com/api/webhook/github
Events: Push, Pull Request
Content Type: application/json
Secret: your-webhook-secret
Status: ✅ Auto-created during repo creation
```

### **Repository_B Webhook** (existing)
```
URL: https://your-dev-portal.com/api/webhook/github
Events: Push
Content Type: application/json
Secret: your-webhook-secret
Status: Manual setup required
```

## 📈 **LỢI ÍCH**

### **1. Centralized Management**
- Tất cả YAML manifests được quản lý tập trung trong MongoDB
- Không cần Repository_B cho việc lưu trữ manifests
- Dễ dàng backup và restore

### **2. Real-time Updates**
- Webhook từ Repository_A → Dev Portal ngay lập tức
- MongoDB cập nhật YAML → ArgoCD sync ngay
- Giảm latency đáng kể

### **3. Better Tracking**
- Lưu trữ history của tất cả changes
- Audit trail đầy đủ
- Version control cho YAML manifests

### **4. Fallback Mechanism**
- Tự động fallback sang Repository_B nếu ArgoCD sync thất bại
- Đảm bảo deployment không bị gián đoạn
- High availability

## 🚨 **TROUBLESHOOTING**

### **1. MongoDB Connection Issues**
```bash
# Check MongoDB connection
curl http://localhost:8000/api/yaml-manifests
```

### **2. ArgoCD Sync Issues**
```bash
# Check ArgoCD sync status
curl http://localhost:8000/api/yaml-manifests/{app_name}/status
```

### **3. Webhook Issues**
```bash
# Check webhook health
curl http://localhost:8000/api/webhook/health

# Check webhook setup in repository
curl -H "Authorization: token YOUR_GITHUB_TOKEN" \
  https://api.github.com/repos/USER/REPO/hooks

# Test webhook manually
curl -X POST http://localhost:8000/api/webhook/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: push" \
  -d '{"ref":"refs/heads/main","repository":{"name":"test-repo"}}'
```

### **4. Fallback to Repository_B**
```bash
# Force fallback sync
curl -X POST "http://localhost:8000/api/yaml-manifests/{app_name}/sync?use_fallback=true"
```

## 🔄 **MIGRATION TỪ LUỒNG CŨ**

### **1. Backup Existing Data**
```bash
# Backup Repository_B manifests
git clone https://github.com/user/repository-b.git
```

### **2. Enable MongoDB YAML Storage**
```bash
# Update environment variables
export MONGODB_URL=mongodb://localhost:27017
export MONGODB_DATABASE=argocd_apps
```

### **3. Migrate Existing Manifests**
```bash
# Use migration script to move manifests from Repository_B to MongoDB
python migrate_manifests_to_mongodb.py
```

### **4. Update Webhooks**
- Add Repository_A webhook URL
- Keep existing Repository_B webhook for fallback

## 📊 **MONITORING**

### **1. MongoDB Metrics**
- YAML manifests count
- Sync status distribution
- Error rates

### **2. ArgoCD Metrics**
- Application sync status
- Sync duration
- Error rates

### **3. Webhook Metrics**
- Webhook delivery success rate
- Processing time
- Error rates

## 🎯 **KẾT LUẬN**

Luồng mới MongoDB YAML Sync cung cấp:

✅ **Centralized Management** - MongoDB làm trung tâm  
✅ **Real-time Updates** - Webhook → MongoDB → ArgoCD  
✅ **Better Tracking** - History và audit trail  
✅ **High Availability** - Fallback mechanism  
✅ **Simplified Architecture** - Bỏ Repository_B dependency  

**Luồng này hoàn toàn khả thi và tối ưu hơn luồng cũ!**
