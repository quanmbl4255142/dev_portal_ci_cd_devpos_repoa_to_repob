# 🚀 GitHub Webhook Setup để giảm thời gian ArgoCD sync

## 🎯 Mục tiêu
Giảm thời gian từ **15+ phút** xuống **2-3 phút** bằng cách trigger ArgoCD sync ngay lập tức khi có push vào Repository_B.

## 📋 Các bước cấu hình

### 1. Cấu hình GitHub Webhook

**Bước 1: Vào GitHub Repository Settings**
- Vào repository: `https://github.com/quanmbl4255142/repository_b_ci_cd_fpt_repob_devops`
- Settings → Webhooks → Add webhook

**Bước 2: Cấu hình Webhook**
```
Payload URL: https://your-dev-portal-domain.com/api/webhook/github
Content type: application/json
Secret: your-webhook-secret (tạo random string)
Events: Chỉ chọn "Pushes"
```

**Bước 3: Test Webhook**
- GitHub sẽ gửi ping event để test
- Check logs trong Dev Portal để confirm webhook hoạt động

### 2. Cập nhật ArgoCD ApplicationSet

**File đã được cập nhật:** `repository_b_ci_cd_fpt_repob_devops/k8s/applicationset.yaml`

```yaml
spec:
  generators:
  - git:
      repoURL: https://github.com/quanmbl4255142/repository_b_ci_cd_fpt_repob_devops.git
      revision: main
      directories:
      - path: apps/*
      # Tối ưu: Refresh nhanh hơn để detect app mới sớm hơn
      refresh: 30s
```

**Apply changes:**
```bash
kubectl apply -f repository_b_ci_cd_fpt_repob_devops/k8s/applicationset.yaml
```

### 3. Cấu hình Environment Variables

**Trong Dev Portal Service:**
```bash
# ArgoCD Configuration
ARGOCD_SERVER_URL=https://your-argocd-domain.com
ARGOCD_TOKEN=your-argocd-token

# GitHub Webhook Configuration  
GITHUB_WEBHOOK_SECRET=your-webhook-secret
```

### 4. Test Quy trình

**Test Flow:**
1. Tạo app mới từ Dev Portal Form
2. Check GitHub Repository_B có folder mới trong `apps/`
3. GitHub webhook sẽ trigger ngay lập tức
4. ArgoCD sẽ detect và deploy trong 2-3 phút thay vì 15+ phút

## 🔧 Troubleshooting

### Webhook không hoạt động
```bash
# Check webhook logs
curl -X GET https://your-dev-portal-domain.com/api/webhook/health

# Check GitHub webhook deliveries
# Vào GitHub → Settings → Webhooks → View recent deliveries
```

### ArgoCD vẫn chậm
```bash
# Check ApplicationSet status
kubectl get applicationset django-apps -n argocd -o yaml

# Check ArgoCD controller logs
kubectl logs -n argocd deployment/argocd-application-controller
```

### Application không được tạo
```bash
# Check ArgoCD applications
kubectl get applications -n argocd

# Check ApplicationSet generator
kubectl describe applicationset django-apps -n argocd
```

## 📊 Monitoring

### Dashboard Metrics
- Truy cập Dashboard để monitor sync status
- Check "Last Synced" time trong ArgoCD applications
- Monitor webhook delivery success rate

### Logs
```bash
# Dev Portal logs
docker logs dev-portal-service

# ArgoCD logs  
kubectl logs -n argocd deployment/argocd-application-controller
```

## 🎉 Kết quả mong đợi

**Trước khi tối ưu:**
- Push code → ArgoCD detect → 15+ phút
- Manual sync required

**Sau khi tối ưu:**
- Push code → GitHub webhook → ArgoCD sync → 2-3 phút
- Automatic sync triggered

## 🔄 Backup Plan

Nếu webhook không hoạt động, vẫn có thể:
1. Manual sync từ ArgoCD UI
2. Force sync từ Dashboard: `/api/dashboard/sync`
3. ApplicationSet vẫn sẽ detect changes sau 30s (thay vì 3 phút mặc định)
