"""
K8s Manifests Generator for Repository_B
Generates Kubernetes manifests for deployment to Repository_B multi-app structure
"""
from typing import Dict
from datetime import datetime


class K8sManifestsGenerator:
    """Generator for K8s manifests compatible with Repository_B"""
    
    def __init__(self, app_name: str, namespace: str, docker_image: str, 
                 repo_b_url: str = None, port: int = 8000, project_module_name: str = None):
        self.app_name = app_name
        self.namespace = namespace
        self.docker_image = docker_image
        self.repo_b_url = repo_b_url or "https://github.com/your-username/Repository_B.git"
        self.port = port
        # Module name for Django (e.g., "django_api", "test_argocd_1")
        self.project_module_name = project_module_name or app_name.replace('-', '_')
    
    def generate_namespace(self) -> str:
        """Generate namespace.yaml"""
        return f'''apiVersion: v1
kind: Namespace
metadata:
  name: {self.namespace}
  labels:
    name: {self.namespace}
    managed-by: dev-portal
'''
    
    def generate_deployment(self) -> str:
        """Generate deployment.yaml with Image Updater annotations"""
        timestamp = int(datetime.now().timestamp())
        
        return f'''apiVersion: apps/v1
kind: Deployment
metadata:
  name: {self.app_name}
  namespace: {self.namespace}
  labels:
    app: {self.app_name}
    environment: production
  annotations:
    argocd-image-updater.argoproj.io/image-list: {self.app_name}={self.docker_image}
    argocd-image-updater.argoproj.io/write-back-method: git
    argocd-image-updater.argoproj.io/write-back-target: apps/{self.app_name}/deployment.yaml
    argocd-image-updater.argoproj.io/{self.app_name}.update-strategy: latest
    argocd-image-updater.argoproj.io/{self.app_name}.allow-tags: regexp:^.*$
spec:
  replicas: 2
  selector:
    matchLabels:
      app: {self.app_name}
  template:
    metadata:
      labels:
        app: {self.app_name}
        environment: production
      annotations:
        timestamp: "{timestamp}"
    spec:
      initContainers:
      - name: init-data-dir
        image: busybox:latest
        command: ['sh', '-c', 'mkdir -p /app/data && chmod 777 /app/data']
        volumeMounts:
        - name: {self.app_name}-data
          mountPath: /app/data
      containers:
      - name: {self.app_name}
        image: {self.docker_image}:latest
        command: ["/bin/sh", "-c"]
        args:
          - |
            python manage.py migrate --noinput
            python manage.py collectstatic --noinput
            gunicorn --bind 0.0.0.0:{self.port} {self.project_module_name}.wsgi:application
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "sleep 5"]
        ports:
        - containerPort: {self.port}
        env:
        - name: DJANGO_SETTINGS_MODULE
          value: "{self.project_module_name}.settings"
        - name: ENVIRONMENT
          value: "production"
        volumeMounts:
        - name: {self.app_name}-data
          mountPath: /app/data
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /api/health/
            port: {self.port}
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/health/
            port: {self.port}
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: {self.app_name}-data
        persistentVolumeClaim:
          claimName: {self.app_name}-pvc
'''
    
    def generate_service(self) -> str:
        """Generate service.yaml"""
        return f'''apiVersion: v1
kind: Service
metadata:
  name: {self.app_name}-service
  namespace: {self.namespace}
  labels:
    app: {self.app_name}
spec:
  type: ClusterIP
  ports:
  - port: {self.port}
    targetPort: {self.port}
    protocol: TCP
    name: http
  selector:
    app: {self.app_name}
'''
    
    def generate_pvc(self) -> str:
        """Generate pvc.yaml"""
        return f'''apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {self.app_name}-pvc
  namespace: {self.namespace}
  labels:
    app: {self.app_name}
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
  storageClassName: standard
'''
    
    def generate_ingress(self, domain: str = None) -> str:
        """Generate ingress.yaml"""
        if not domain:
            domain = f"{self.app_name}.yourdomain.com"
        
        return f'''apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {self.app_name}-ingress
  namespace: {self.namespace}
  labels:
    app: {self.app_name}
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - {domain}
    secretName: {self.app_name}-tls
  rules:
  - host: {domain}
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: {self.app_name}-service
            port:
              number: {self.port}
'''
    
    def generate_kustomization(self) -> str:
        """Generate kustomization.yaml"""
        return f'''apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
- namespace.yaml
- pvc.yaml
- deployment.yaml
- service.yaml
- ingress.yaml

# commonLabels không áp dụng cho selector (immutable)
# Chỉ áp dụng cho metadata labels
commonLabels:
  version: v1.0.0
  managed-by: dev-portal

namespace: {self.namespace}
'''
    
    def generate_argocd_application(self) -> str:
        """Generate ArgoCD Application YAML"""
        return f'''apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: {self.app_name}-app
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  source:
    repoURL: {self.repo_b_url}
    targetRevision: HEAD
    path: apps/{self.app_name}
  destination:
    server: https://kubernetes.default.svc
    namespace: {self.namespace}
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
      allowEmpty: false
    syncOptions:
    - CreateNamespace=true
    - PrunePropagationPolicy=foreground
    - PruneLast=true
  revisionHistoryLimit: 3
'''
    
    def generate_readme(self) -> str:
        """Generate README for the manifests"""
        return f'''# {self.app_name} - Kubernetes Manifests

Generated by Django Dev Portal

## 📦 Deployment Information

- **Application**: {self.app_name}
- **Namespace**: {self.namespace}
- **Docker Image**: {self.docker_image}
- **Port**: {self.port}

## 📁 Files

- `namespace.yaml` - Kubernetes namespace
- `deployment.yaml` - Application deployment with 2 replicas
- `service.yaml` - ClusterIP service
- `pvc.yaml` - PersistentVolumeClaim (1Gi)
- `ingress.yaml` - Ingress configuration
- `kustomization.yaml` - Kustomize configuration
- `argocd-application.yaml` - ArgoCD Application definition

## 🚀 Deployment to Repository_B (Multi-App Structure)

### Step 1: Add to Repository_B

```bash
# Clone Repository_B
git clone {self.repo_b_url}
cd Repository_B

# Copy manifests to apps/<app-name>/ directory
mkdir -p apps/{self.app_name}
cp <this-directory>/*.yaml apps/{self.app_name}/

# Commit and push
git add apps/{self.app_name}/
git commit -m "Add {self.app_name} manifests"
git push origin main
```

### Step 2: ArgoCD Auto-Deploys

ArgoCD ApplicationSet tự động:
- Phát hiện app mới trong `apps/{self.app_name}/`
- Tạo Application `{self.app_name}`
- Deploy vào namespace `{self.app_name}`

```bash
# Check Applications
kubectl get applications -n argocd

# Watch sync
kubectl get app {self.app_name} -n argocd -w
```

### Step 3: Verify Deployment

```bash
# Check pods
kubectl get pods -n {self.namespace}

# Check service
kubectl get svc -n {self.namespace}

# Check ingress
kubectl get ingress -n {self.namespace}

# View logs
kubectl logs -f deployment/{self.app_name} -n {self.namespace}
```

## 🔄 Auto-Deployment Workflow

1. Push code to your app repository
2. GitHub Actions builds Docker image
3. Image pushed to registry: {self.docker_image}
4. ArgoCD Image Updater detects new image
5. Updates deployment.yaml in Repository_B
6. ArgoCD syncs changes
7. New pods deployed automatically

## 🛠️ Manual Operations

### Force sync
```bash
kubectl patch app {self.app_name} -n argocd \\
  -p '{{"metadata":{{"annotations":{{"argocd.argoproj.io/refresh":"hard"}}}}}}' \\
  --type merge
```

### Restart deployment
```bash
kubectl rollout restart deployment/{self.app_name} -n {self.namespace}
```

### Scale replicas
```bash
kubectl scale deployment/{self.app_name} -n {self.namespace} --replicas=3
```

### Delete application
```bash
kubectl delete app {self.app_name} -n argocd
kubectl delete namespace {self.namespace}
```

## 📊 Monitoring

### Health Check
```bash
curl http://<ingress-host>/api/health/
```

### Resource Usage
```bash
kubectl top pods -n {self.namespace}
```

### Events
```bash
kubectl get events -n {self.namespace} --sort-by='.lastTimestamp'
```

## 🔧 Customization

### Update replicas
Edit `deployment.yaml`:
```yaml
spec:
  replicas: 3  # Change this
```

### Update resources
Edit `deployment.yaml`:
```yaml
resources:
  requests:
    memory: "512Mi"  # Increase
    cpu: "500m"
  limits:
    memory: "1Gi"
    cpu: "1000m"
```

### Update domain
Edit `ingress.yaml`:
```yaml
spec:
  rules:
  - host: your-custom-domain.com  # Change this
```

## 📚 Documentation

- [Repository_B Multi-App Guide](../GIAI-PHAP-REPOSITORY-B.md)
- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)

---

**Generated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
**Tool**: Django Dev Portal v1.0.0
'''
    
    def generate_argocd_image_updater_config(self) -> str:
        """Generate ArgoCD Image Updater ConfigMap"""
        registry = self.docker_image.split("/")[0]
        return f'''apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-image-updater-config
  namespace: argocd  # ĐÚNG NAMESPACE
data:
  registries.conf: |
    registries:
    - name: GitHub Container Registry
      prefix: {registry}
      api_url: https://{registry}
      credentials: secret:argocd/{self.app_name}#.dockerconfigjson
      default: true
  git.user: "your-username"
  git.email: "your-email@example.com"
  git.commit-message: "chore: update image to {{.ImageName}}:{{.ImageTag}}"
  git.commit-user-name: "ArgoCD Image Updater"
  git.commit-user-email: "argocd-image-updater@example.com"
'''
    
    def generate_all(self) -> Dict[str, str]:
        """Generate all K8s manifests for multi-app structure"""
        manifests = {
            # Core manifests - được push vào apps/<app-name>/ trong Repository_B
            'namespace.yaml': self.generate_namespace(),
            'deployment.yaml': self.generate_deployment(),
            'service.yaml': self.generate_service(),
            'pvc.yaml': self.generate_pvc(),
            'ingress.yaml': self.generate_ingress(),
            'kustomization.yaml': self.generate_kustomization(),
            'README.md': self.generate_readme(),
            
            # ArgoCD Application - CHỈ để reference, KHÔNG push
            # ApplicationSet trong k8s/applicationset.yaml sẽ tự tạo Application
            'argocd-application.yaml': self.generate_argocd_application(),
            
            # NOTE: Multi-app structure trong Repository_B:
            # - apps/django-api/    -> namespace: django-api
            # - apps/app-2/         -> namespace: app-2
            # - apps/app-n/         -> namespace: app-n
            # Mỗi app có namespace RIÊNG, không đè lên nhau
        }
        
        return manifests

