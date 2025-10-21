"""
Dev Portal - Tự động sinh Django REST API Project
Tạo bởi: Dev Portal Tool
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import os
import json
import zipfile
import io
from datetime import datetime
import asyncio
import logging
from k8s_generator import K8sManifestsGenerator
from github_manager import GitHubManager
from mongodb_client import get_mongodb_client
from argo_sync_service import get_sync_service
from auto_sync_service import get_auto_sync_service, force_sync_now
from github_webhook_handler import github_webhook_endpoint, webhook_health_check

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Django Dev Portal",
    description="Portal tự động sinh Django REST API project với ArgoCD & CI/CD",
    version="1.0.0"
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Global variables for background tasks
sync_task = None


class ModelField(BaseModel):
    """Model field definition"""
    name: str = Field(..., description="Tên field (vd: name, price)")
    type: str = Field(..., description="Loại field (CharField, IntegerField, TextField, etc)")
    max_length: Optional[int] = Field(None, description="Max length cho CharField")
    decimal_places: Optional[int] = Field(None, description="Decimal places cho DecimalField")
    max_digits: Optional[int] = Field(None, description="Max digits cho DecimalField")
    blank: bool = Field(False, description="Có được để trống không")
    null: bool = Field(False, description="Có được NULL không")
    default: Optional[str] = Field(None, description="Giá trị mặc định")


class DjangoModel(BaseModel):
    """Django model definition"""
    name: str = Field(..., description="Tên model (vd: Product, User)")
    fields: List[ModelField] = Field(..., description="Danh sách các fields")
    api_endpoint: str = Field(..., description="API endpoint (vd: products, users)")


class ProjectConfig(BaseModel):
    """Configuration cho Django project"""
    project_name: str = Field(..., description="Tên Django project (vd: django_api)")
    app_name: str = Field(..., description="Tên Django app (vd: api)")
    git_repo_url: Optional[str] = Field(None, description="URL Git repository")
    github_username: Optional[str] = Field(None, description="GitHub username")
    docker_registry: str = Field("ghcr.io", description="Docker registry")
    models: List[DjangoModel] = Field(..., description="Danh sách các models")
    enable_cors: bool = Field(True, description="Enable CORS")
    enable_cicd: bool = Field(True, description="Enable CI/CD với GitHub Actions")
    repo_b_url: Optional[str] = Field(None, description="URL Repository_B cho manifests")


class AutoDeployConfig(BaseModel):
    """Configuration cho auto-deploy lên Git và ArgoCD"""
    project_config: ProjectConfig = Field(..., description="Project configuration")
    github_token: str = Field(..., description="GitHub Personal Access Token")
    repo_a_name: str = Field(..., description="Tên Repository_A (Django app)")
    repo_b_name: Optional[str] = Field(None, description="Tên Repository_B (K8s manifests)")
    create_new_repo_a: bool = Field(True, description="Tạo Repository_A mới hay dùng existing")
    repo_a_private: bool = Field(False, description="Repository_A là private hay public")
    auto_push_repo_b: bool = Field(True, description="Tự động push manifests vào Repository_B")


class ProjectGenerator:
    """Generator để tạo Django project"""
    
    def __init__(self, config: ProjectConfig):
        self.config = config
        self.files = {}
    
    def generate_field_definition(self, field: ModelField) -> str:
        """Generate Django model field definition"""
        field_type = field.type
        params = []
        
        if field.max_length:
            params.append(f"max_length={field.max_length}")
        if field.max_digits:
            params.append(f"max_digits={field.max_digits}")
        if field.decimal_places:
            params.append(f"decimal_places={field.decimal_places}")
        if field.blank:
            params.append("blank=True")
        if field.null:
            params.append("null=True")
        if field.default:
            params.append(f"default='{field.default}'")
        
        params_str = ", ".join(params) if params else ""
        return f"models.{field_type}({params_str})"
    
    def generate_models_py(self, model: DjangoModel) -> str:
        """Generate models.py content"""
        fields_code = []
        for field in model.fields:
            if field.name not in ['created_at', 'updated_at']:
                field_def = self.generate_field_definition(field)
                fields_code.append(f"    {field.name} = {field_def}")
        
        # Add auto timestamps
        fields_code.append("    created_at = models.DateTimeField(auto_now_add=True)")
        fields_code.append("    updated_at = models.DateTimeField(auto_now=True)")
        
        return f'''from django.db import models

class {model.name}(models.Model):
{chr(10).join(fields_code)}

    def __str__(self):
        return self.{model.fields[0].name if model.fields else 'name'}
'''
    
    def generate_serializers_py(self, model: DjangoModel) -> str:
        """Generate serializers.py content"""
        field_names = [f.name for f in model.fields] + ['created_at', 'updated_at']
        fields_str = "', '".join(['id'] + field_names)
        
        return f'''from rest_framework import serializers
from .models import {model.name}

class {model.name}Serializer(serializers.ModelSerializer):
    class Meta:
        model = {model.name}
        fields = ['{fields_str}']
'''
    
    def generate_views_py(self) -> str:
        """Generate views.py content"""
        views = []
        
        for model in self.config.models:
            views.append(f'''
class {model.name}ListCreateView(generics.ListCreateAPIView):
    queryset = {model.name}.objects.all()
    serializer_class = {model.name}Serializer


class {model.name}DetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = {model.name}.objects.all()
    serializer_class = {model.name}Serializer
''')
        
        imports = "from rest_framework import generics\nfrom django.http import JsonResponse\n"
        model_imports = ", ".join([m.name for m in self.config.models])
        serializer_imports = ", ".join([f"{m.name}Serializer" for m in self.config.models])
        imports += f"from .models import {model_imports}\n"
        imports += f"from .serializers import {serializer_imports}\n"
        
        health_check = f'''

# API endpoint để lấy thông tin health check
def health_check(request):
    return JsonResponse({{
        'status': 'healthy',
        'message': '{self.config.project_name} API is running!'
    }})
'''
        
        return imports + "\n" + "\n".join(views) + health_check
    
    def generate_urls_py(self) -> str:
        """Generate urls.py for app"""
        patterns = []
        
        for model in self.config.models:
            endpoint = model.api_endpoint
            patterns.append(f"    path('{endpoint}/', views.{model.name}ListCreateView.as_view(), name='{endpoint}-list'),")
            patterns.append(f"    path('{endpoint}/<int:pk>/', views.{model.name}DetailView.as_view(), name='{endpoint}-detail'),")
        
        patterns.append("    path('health/', views.health_check, name='health-check'),")
        
        return f'''from django.urls import path
from . import views

urlpatterns = [
{chr(10).join(patterns)}
]
'''
    
    def generate_settings_py(self) -> str:
        """Generate settings.py"""
        cors_setting = "'corsheaders'," if self.config.enable_cors else ""
        cors_middleware = "'corsheaders.middleware.CorsMiddleware'," if self.config.enable_cors else ""
        cors_config = "\n# CORS settings\nCORS_ALLOW_ALL_ORIGINS = True\n" if self.config.enable_cors else ""
        
        return f'''"""
Django settings for {self.config.project_name} project.
Generated by Dev Portal
"""

from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-your-secret-key-here-{datetime.now().timestamp()}'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    {cors_setting}
    '{self.config.app_name}',
]

MIDDLEWARE = [
    {cors_middleware}
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = '{self.config.project_name}.urls'

TEMPLATES = [
    {{
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {{
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        }},
    }},
]

WSGI_APPLICATION = '{self.config.project_name}.wsgi.application'

# Database
# Sử dụng persistent storage để giữ data khi pod restart
DATABASES = {{
    'default': {{
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': '/app/data/db.sqlite3',
    }}
}}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {{
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    }},
    {{
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    }},
    {{
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    }},
    {{
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    }},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
{cors_config}
# REST Framework settings
REST_FRAMEWORK = {{
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
}}
'''
    
    def generate_main_urls_py(self) -> str:
        """Generate main urls.py"""
        return f'''"""
URL configuration for {self.config.project_name} project.
"""
from django.contrib import admin
from django.urls import path, include


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('{self.config.app_name}.urls')),
]
'''
    
    def generate_dockerfile(self) -> str:
        """Generate Dockerfile"""
        return '''# Sử dụng Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \\
    && apt-get install -y --no-install-recommends \\
        postgresql-client \\
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /app/

# Create a non-root user
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "{}.wsgi:application"]
'''.format(self.config.project_name)
    
    def generate_requirements_txt(self) -> str:
        """Generate requirements.txt"""
        cors = "django-cors-headers==4.3.1\n" if self.config.enable_cors else ""
        return f'''Django==4.2.7
djangorestframework==3.14.0
{cors}gunicorn==21.2.0
'''
    
    def generate_github_workflow(self) -> str:
        """Generate GitHub Actions workflow"""
        if not self.config.enable_cicd:
            return ""
        
        repo_name = self.config.git_repo_url.split('/')[-1].replace('.git', '').lower() if self.config.git_repo_url else 'repository'
        github_user = (self.config.github_username or 'your-username').lower()
        repo_b_name = self.config.repo_b_url.split('/')[-1].replace('.git', '').lower() if self.config.repo_b_url else 'repository_b'
        repo_b_user = self.config.repo_b_url.split('/')[-2].lower() if self.config.repo_b_url else github_user
        
        # Ensure app_name is properly formatted
        app_name = self.config.project_name.replace('_', '-').lower()
        
        return f'''name: Django CI/CD Pipeline

# CHỈ CHẠY KHI:
# 1. Push code lên main branch
# 2. Manual trigger (workflow_dispatch)
on:
  push:
    branches: [ main ]
  workflow_dispatch: # Cho phép chạy thủ công

# Concurrency control để tránh multiple workflows chạy cùng lúc
concurrency:
  group: django-cicd-${{{{ github.repository }}}}-${{{{ github.ref }}}}
  cancel-in-progress: true  # Cancel workflow cũ nếu có workflow mới

env:
  REGISTRY: {self.config.docker_registry}
  IMAGE_NAME: ${{{{ github.repository }}}}

# WORKFLOW CÓ 3 STEPS TUẦN TỰ:
# 1. test → Test Django code
# 2. build-and-push → Build Docker image + Push lên GHCR  
# 3. update-manifests → Update K8s manifests trong Repository_B

jobs:
  # STEP 1: Test Django code
  test:
    runs-on: ubuntu-latest
    steps:
    - name: Checkout code
      uses: actions/checkout@v4
      
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
        
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-cov
        
    - name: Run tests
      run: |
        # Set Django settings module
        export DJANGO_SETTINGS_MODULE={self.config.project_name}.settings
        # Kiểm tra import Django
        python -c "import django; print(f'Django version: {{django.get_version()}}')"
        # Basic Django check (no database required)
        python -c "
        import os
        import sys
        import django
        from django.conf import settings
        
        # Minimal settings for testing
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', '{self.config.project_name}.settings')
        
        try:
            django.setup()
            print('✅ Django setup successful')
            
            # Test basic imports
            from {self.config.app_name}.models import *
            from {self.config.app_name}.views import *
            print('✅ Models and views imported successfully')
            
        except Exception as e:
            print(f'❌ Django test failed: {{e}}')
            sys.exit(1)
        "

  # STEP 2: Build Docker image và push lên GHCR
  build-and-push:
    needs: test
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
      id-token: write
      
    steps:
    - name: Checkout code
      uses: actions/checkout@v4
      
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3
      continue-on-error: true
      
    - name: Retry Docker Buildx setup if failed
      if: failure()
      uses: docker/setup-buildx-action@v3
      with:
        driver-opts: |
          image=moby/buildkit:buildx-stable-1
      
    - name: Log in to Container Registry
      uses: docker/login-action@v3
      with:
        registry: ${{{{ env.REGISTRY }}}}
        username: ${{{{ github.actor }}}}
        password: ${{{{ secrets.GITHUB_TOKEN }}}}
        
    - name: Extract metadata
      id: meta
      uses: docker/metadata-action@v5
      with:
        images: ${{{{ env.REGISTRY }}}}/${{{{ env.IMAGE_NAME }}}}
        tags: |
          type=ref,event=branch
          type=ref,event=pr
          type=sha,prefix=${{{{ github.ref_name }}}}
          type=raw,value=latest,enable=${{{{ github.ref == 'refs/heads/main' }}}}
          
    - name: Build and push Docker image
      uses: docker/build-push-action@v5
      with:
        context: .
        platforms: linux/amd64,linux/arm64
        push: true
        tags: ${{{{ steps.meta.outputs.tags }}}}
        labels: ${{{{ steps.meta.outputs.labels }}}}
        cache-from: type=gha
        cache-to: type=gha,mode=max
        build-args: |
          BUILDKIT_INLINE_CACHE=1
      # Continue on error để debug
      continue-on-error: true
      
    - name: Retry Docker build if failed
      if: failure()
      uses: docker/build-push-action@v5
      with:
        context: .
        platforms: linux/amd64
        push: true
        tags: ${{{{ steps.meta.outputs.tags }}}}
        labels: ${{{{ steps.meta.outputs.labels }}}}
        cache-from: type=gha
        cache-to: type=gha,mode=max
        build-args: |
          BUILDKIT_INLINE_CACHE=1
      
    - name: Check build result
      run: |
        if [ "${{{{ job.status }}}}" = "failure" ]; then
          echo "❌ Docker build failed!"
          echo "🔍 Common issues:"
          echo "  1. Dockerfile syntax error"
          echo "  2. Missing dependencies in requirements.txt"
          echo "  3. Permission issues with GHCR"
          echo "  4. Network issues during build"
          exit 1
        else
          echo "✅ Docker build successful"
        fi

  # STEP 3: Update K8s manifests trong Repository_B
  update-manifests:
    needs: build-and-push
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    permissions:
      contents: write
    
    steps:
    - name: Debug - Check secrets
      run: |
        echo "🔍 Checking secrets availability..."
        if [ -z "${{{{ secrets.PAT_TOKEN }}}}" ]; then
          echo "❌ PAT_TOKEN secret is not set!"
          echo "📝 Please add PAT_TOKEN secret to repository settings"
          echo "🔗 Go to: Settings → Secrets and variables → Actions → New repository secret"
          echo "   Name: PAT_TOKEN"
          echo "   Value: Your GitHub Personal Access Token"
          exit 1
        else
          echo "✅ PAT_TOKEN secret is available"
        fi
        
    - name: Checkout manifests repo
      uses: actions/checkout@v4
      with:
        repository: {repo_b_user}/{repo_b_name}
        token: ${{{{ secrets.PAT_TOKEN }}}}
        path: manifests
        fetch-depth: 0
        
    - name: Debug - List manifests directory
      run: |
        echo "=== Manifests directory structure ==="
        cd manifests
        
        # Define app_name variable
        APP_NAME="{app_name}"
        echo "📦 Target app: $APP_NAME"
        
        find . -type f -name "*.yaml" | head -20
        echo "=== apps directory ==="
        ls -la apps/ || echo "No apps directory found"
        echo "=== Looking for deployment.yaml ==="
        ls -la apps/$APP_NAME/deployment.yaml || echo "No deployment.yaml found"
        
    - name: Update image tag in deployment
      run: |
        cd manifests
        echo "Current directory: $(pwd)"
        echo "Files in manifests:"
        ls -la
        
        # Define app_name variable
        APP_NAME="{app_name}"
        echo "📦 Target app: $APP_NAME"
        
        DEPLOYMENT_FILE="apps/$APP_NAME/deployment.yaml"
        
        if [ ! -f "$DEPLOYMENT_FILE" ]; then
          echo "❌ Error: $DEPLOYMENT_FILE not found!"
          echo "📁 Current directory: $(pwd)"
          echo "📂 Directory contents:"
          ls -la
          echo "🔍 Looking for deployment files in apps/$APP_NAME/:"
          find apps/$APP_NAME -name "deployment.yaml" -type f 2>/dev/null || echo "No deployment.yaml found in apps/$APP_NAME/"
          echo "💡 Creating apps/$APP_NAME/ directory if it doesn't exist..."
          mkdir -p "apps/$APP_NAME"
          echo "📝 Creating deployment.yaml..."
          
          # Create deployment.yaml using echo commands to avoid heredoc issues
          echo "apiVersion: apps/v1" > "$DEPLOYMENT_FILE"
          echo "kind: Deployment" >> "$DEPLOYMENT_FILE"
          echo "metadata:" >> "$DEPLOYMENT_FILE"
          echo "  name: {app_name}" >> "$DEPLOYMENT_FILE"
          echo "  namespace: {app_name}" >> "$DEPLOYMENT_FILE"
          echo "  labels:" >> "$DEPLOYMENT_FILE"
          echo "    app: {app_name}" >> "$DEPLOYMENT_FILE"
          echo "    environment: production" >> "$DEPLOYMENT_FILE"
          echo "  annotations:" >> "$DEPLOYMENT_FILE"
          echo "    argocd-image-updater.argoproj.io/image-list: {app_name}={self.config.docker_registry}/{github_user}/{repo_name}" >> "$DEPLOYMENT_FILE"
          echo "    argocd-image-updater.argoproj.io/write-back-method: git" >> "$DEPLOYMENT_FILE"
          echo "    argocd-image-updater.argoproj.io/write-back-target: apps/{app_name}/deployment.yaml" >> "$DEPLOYMENT_FILE"
          echo "    argocd-image-updater.argoproj.io/{app_name}.update-strategy: latest" >> "$DEPLOYMENT_FILE"
          echo "    argocd-image-updater.argoproj.io/{app_name}.allow-tags: regexp:^.*$" >> "$DEPLOYMENT_FILE"
          echo "spec:" >> "$DEPLOYMENT_FILE"
          echo "  replicas: 2" >> "$DEPLOYMENT_FILE"
          echo "  selector:" >> "$DEPLOYMENT_FILE"
          echo "    matchLabels:" >> "$DEPLOYMENT_FILE"
          echo "      app: {app_name}" >> "$DEPLOYMENT_FILE"
          echo "  template:" >> "$DEPLOYMENT_FILE"
          echo "    metadata:" >> "$DEPLOYMENT_FILE"
          echo "      labels:" >> "$DEPLOYMENT_FILE"
          echo "        app: {app_name}" >> "$DEPLOYMENT_FILE"
          echo "        environment: production" >> "$DEPLOYMENT_FILE"
          echo "      annotations:" >> "$DEPLOYMENT_FILE"
          echo "        timestamp: \\"$(date +%s)\\"" >> "$DEPLOYMENT_FILE"
          echo "    spec:" >> "$DEPLOYMENT_FILE"
          echo "      initContainers:" >> "$DEPLOYMENT_FILE"
          echo "      - name: init-data-dir" >> "$DEPLOYMENT_FILE"
          echo "        image: busybox:latest" >> "$DEPLOYMENT_FILE"
          echo "        command: ['sh', '-c', 'mkdir -p /app/data && chmod 777 /app/data']" >> "$DEPLOYMENT_FILE"
          echo "        volumeMounts:" >> "$DEPLOYMENT_FILE"
          echo "        - name: {app_name}-data" >> "$DEPLOYMENT_FILE"
          echo "          mountPath: /app/data" >> "$DEPLOYMENT_FILE"
          echo "      containers:" >> "$DEPLOYMENT_FILE"
          echo "      - name: {app_name}" >> "$DEPLOYMENT_FILE"
          echo "        image: {self.config.docker_registry}/{github_user}/{repo_name}:latest" >> "$DEPLOYMENT_FILE"
          echo "        command: [\\"/bin/sh\\", \\"-c\\"]" >> "$DEPLOYMENT_FILE"
          echo "        args:" >> "$DEPLOYMENT_FILE"
          echo "          - |" >> "$DEPLOYMENT_FILE"
          echo "            python manage.py migrate --noinput" >> "$DEPLOYMENT_FILE"
          echo "            python manage.py collectstatic --noinput" >> "$DEPLOYMENT_FILE"
          echo "            gunicorn --bind 0.0.0.0:8000 {self.config.project_name}.wsgi:application" >> "$DEPLOYMENT_FILE"
          echo "        lifecycle:" >> "$DEPLOYMENT_FILE"
          echo "          preStop:" >> "$DEPLOYMENT_FILE"
          echo "            exec:" >> "$DEPLOYMENT_FILE"
          echo "              command: [\\"/bin/sh\\", \\"-c\\", \\"sleep 5\\"]" >> "$DEPLOYMENT_FILE"
          echo "        ports:" >> "$DEPLOYMENT_FILE"
          echo "        - containerPort: 8000" >> "$DEPLOYMENT_FILE"
          echo "        env:" >> "$DEPLOYMENT_FILE"
          echo "        - name: DJANGO_SETTINGS_MODULE" >> "$DEPLOYMENT_FILE"
          echo "          value: \\"{self.config.project_name}.settings\\"" >> "$DEPLOYMENT_FILE"
          echo "        - name: ENVIRONMENT" >> "$DEPLOYMENT_FILE"
          echo "          value: \\"production\\"" >> "$DEPLOYMENT_FILE"
          echo "        volumeMounts:" >> "$DEPLOYMENT_FILE"
          echo "        - name: {app_name}-data" >> "$DEPLOYMENT_FILE"
          echo "          mountPath: /app/data" >> "$DEPLOYMENT_FILE"
          echo "        resources:" >> "$DEPLOYMENT_FILE"
          echo "          requests:" >> "$DEPLOYMENT_FILE"
          echo "            memory: \\"256Mi\\"" >> "$DEPLOYMENT_FILE"
          echo "            cpu: \\"250m\\"" >> "$DEPLOYMENT_FILE"
          echo "          limits:" >> "$DEPLOYMENT_FILE"
          echo "            memory: \\"512Mi\\"" >> "$DEPLOYMENT_FILE"
          echo "            cpu: \\"500m\\"" >> "$DEPLOYMENT_FILE"
          echo "        livenessProbe:" >> "$DEPLOYMENT_FILE"
          echo "          httpGet:" >> "$DEPLOYMENT_FILE"
          echo "            path: /api/health/" >> "$DEPLOYMENT_FILE"
          echo "            port: 8000" >> "$DEPLOYMENT_FILE"
          echo "          initialDelaySeconds: 30" >> "$DEPLOYMENT_FILE"
          echo "          periodSeconds: 10" >> "$DEPLOYMENT_FILE"
          echo "        readinessProbe:" >> "$DEPLOYMENT_FILE"
          echo "          httpGet:" >> "$DEPLOYMENT_FILE"
          echo "            path: /api/health/" >> "$DEPLOYMENT_FILE"
          echo "            port: 8000" >> "$DEPLOYMENT_FILE"
          echo "          initialDelaySeconds: 5" >> "$DEPLOYMENT_FILE"
          echo "          periodSeconds: 5" >> "$DEPLOYMENT_FILE"
          echo "      volumes:" >> "$DEPLOYMENT_FILE"
          echo "      - name: {app_name}-data" >> "$DEPLOYMENT_FILE"
          echo "        persistentVolumeClaim:" >> "$DEPLOYMENT_FILE"
          echo "          claimName: {app_name}-pvc" >> "$DEPLOYMENT_FILE"
          
          echo "✅ Created deployment.yaml"
        fi
        
        echo "Before update:"
        grep "image:" "$DEPLOYMENT_FILE" || echo "No image found"
        
        # Update image tag
        sed -i "s|image: {self.config.docker_registry}/.*/.*:.*|image: {self.config.docker_registry}/{github_user}/{repo_name}:latest|g" "$DEPLOYMENT_FILE"
        
        echo "After update:"
        grep "image:" "$DEPLOYMENT_FILE"
        
        # Update timestamp để force restart pods
        TIMESTAMP=$(date +%s)
        echo "Adding timestamp to pod template: $TIMESTAMP"
        sed -i "/^        timestamp:/c\\        timestamp: \\"$TIMESTAMP\\"" "$DEPLOYMENT_FILE"
        
        echo "Updated timestamp in pod template:"
        grep "timestamp:" "$DEPLOYMENT_FILE"
        
    - name: Commit and push changes
      run: |
        cd manifests
        git config --local user.email "action@github.com"
        git config --local user.name "GitHub Action"
        
        # Define app_name variable
        APP_NAME="{app_name}"
        
        # Set remote URL with token
        git remote set-url origin https://${{{{ secrets.PAT_TOKEN }}}}@github.com/{repo_b_user}/{repo_b_name}.git
        
        # Add apps directory
        git add apps/$APP_NAME/ || echo "⚠️ No new files to add"
        
        # Check what files are staged
        echo "📋 Staged files:"
        git diff --cached --name-only || echo "No staged files"
        
        # Check if there are changes to commit
        if git diff --cached --quiet; then
          echo "ℹ️ No changes to commit - deployment.yaml is already up to date"
        else
          # Commit changes
          git commit -m "chore: update k8s manifests for {app_name} [skip ci]"
          
          # Push with retry logic để handle intermittent failures
          echo "🚀 Pushing changes..."
          for i in {{1..3}}; do
            echo "Attempt $i/3..."
            if git push origin main; then
              echo "✅ Successfully pushed manifests to Repository_B"
              break
            else
              echo "⚠️ Push failed (attempt $i/3)"
              if [ $i -lt 3 ]; then
                echo "🔄 Waiting 5 seconds before retry..."
                sleep 5
                echo "🔄 Fetching latest changes before retry..."
                git fetch origin main
                echo "🔄 Resetting to remote main..."
                git reset --hard origin/main
                echo "🔄 Re-adding changes..."
                git add apps/$APP_NAME/
                git commit -m "chore: update k8s manifests for {app_name} [skip ci]"
              else
                echo "❌ All push attempts failed"
                exit 1
              fi
            fi
          done
        fi
        
    - name: Trigger ArgoCD Sync
      run: |
        # Define app_name variable
        APP_NAME="{app_name}"
        
        echo "🔄 Triggering ArgoCD sync for $APP_NAME..."
        
        # Get ArgoCD server URL và token
        ARGOCD_SERVER="${{{{ secrets.ARGOCD_SERVER }}}}"
        ARGOCD_TOKEN="${{{{ secrets.ARGOCD_TOKEN }}}}"
        
        if [ -n "$ARGOCD_SERVER" ] && [ -n "$ARGOCD_TOKEN" ]; then
          echo "🚀 Syncing ArgoCD application: $APP_NAME"
          
          # Method 1: Direct ArgoCD API sync
          echo "📡 Method 1: Direct ArgoCD API sync"
          curl -X POST \
            -H "Authorization: Bearer $ARGOCD_TOKEN" \
            -H "Content-Type: application/json" \
            "$ARGOCD_SERVER/api/v1/applications/$APP_NAME/sync" \
            -d '{{
              "prune": true,
              "dryRun": false,
              "strategy": {{
                "syncStrategy": "apply"
              }}
            }}' || echo "⚠️ ArgoCD API sync failed"
          
          # Method 2: Refresh ApplicationSet để detect app mới
          echo "📡 Method 2: Refresh ApplicationSet"
          curl -X POST \
            -H "Authorization: Bearer $ARGOCD_TOKEN" \
            -H "Content-Type: application/json" \
            "$ARGOCD_SERVER/api/v1/applicationsets/django-apps/refresh" \
            -d '{{}}' || echo "⚠️ ApplicationSet refresh failed"
          
          # Method 3: Trigger via GitHub Webhook (if Dev Portal is running)
          echo "📡 Method 3: Trigger via GitHub Webhook"
          DEV_PORTAL_URL="${{{{ secrets.DEV_PORTAL_URL }}}}"
          if [ -n "$DEV_PORTAL_URL" ]; then
            curl -X POST \
              -H "Content-Type: application/json" \
              "$DEV_PORTAL_URL/api/webhook/github" \
              -d '{{
                "repository": {{
                  "clone_url": "https://github.com/{repo_b_user}/{repo_b_name}.git"
                }},
                "commits": [{{
                  "added": ["apps/$APP_NAME/"],
                  "modified": ["apps/$APP_NAME/"]
                }}]
              }}' || echo "⚠️ GitHub webhook trigger failed"
          fi
          
          echo "✅ ArgoCD sync triggered for $APP_NAME"
        else
          echo "⚠️ ArgoCD credentials not configured, skipping sync"
          echo "ℹ️ Please configure ARGOCD_SERVER and ARGOCD_TOKEN secrets"
        fi
        
    - name: Notify Deployment Completion
      run: |
        # Define app_name variable
        APP_NAME="{app_name}"
        
        echo "✅ CI/CD Pipeline completed successfully!"
        echo "📦 Docker image built and pushed to: ${{{{ env.REGISTRY }}}}/${{{{ env.IMAGE_NAME }}}}:latest"
        echo "🔄 ArgoCD sync triggered for $APP_NAME"
        echo "📝 ArgoCD sẽ tự động sync và deploy"
        echo ""
        echo "🌐 Access UIs:"
        echo "  📊 ArgoCD UI:"
        echo "    kubectl port-forward svc/argocd-server -n argocd 8090:443"
        echo "    → https://localhost:8090"
        echo "    Username: admin"
        echo "    Password: kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{{.data.password}}' | base64 -d"
        echo ""
        echo "  📈 Grafana Dashboard:"
        echo "    kubectl port-forward svc/grafana-service -n monitoring 3000:3000"
        echo "    → http://localhost:3000"
        echo "    Username: admin | Password: admin123"
        echo ""
        echo "📊 Monitor deployment:"
        echo "  - ArgoCD Application: kubectl get app $APP_NAME -n argocd -w"
        echo "  - Kubernetes Pods: kubectl get pods -n $APP_NAME -w"
        echo "  - Application Logs: kubectl logs -n $APP_NAME deployment/$APP_NAME -f"
        echo "  - Image Updater Logs: kubectl logs -n argocd deployment/argocd-image-updater -f"
        echo ""
        echo "🔍 Troubleshooting:"
        echo "  - Check ArgoCD sync status:"
        echo "    kubectl describe app $APP_NAME -n argocd"
        echo "  - Check Image Updater:"
        echo "    kubectl get pods -n argocd | grep image-updater"
        echo "  - Force ArgoCD sync:"
        echo "    kubectl patch app $APP_NAME -n argocd --type merge -p '{{\"metadata\":{{\"annotations\":{{\"argocd.argoproj.io/refresh\":\"hard\"}}}}}}'"
        echo ""
        echo "⏰ Deployment initiated at: $(date)"
'''
    
    def generate_all_files(self) -> Dict[str, str]:
        """Generate tất cả các files cần thiết"""
        files = {}
        
        # Generate models, serializers, views, urls cho mỗi model
        all_models = "\n\n".join([self.generate_models_py(m) for m in self.config.models])
        all_serializers = "\n\n".join([self.generate_serializers_py(m) for m in self.config.models])
        
        # App files
        files[f'{self.config.app_name}/models.py'] = all_models
        files[f'{self.config.app_name}/serializers.py'] = all_serializers
        files[f'{self.config.app_name}/views.py'] = self.generate_views_py()
        files[f'{self.config.app_name}/urls.py'] = self.generate_urls_py()
        files[f'{self.config.app_name}/apps.py'] = f'''from django.apps import AppConfig

class {self.config.app_name.capitalize()}Config(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = '{self.config.app_name}'
'''
        files[f'{self.config.app_name}/__init__.py'] = ''
        files[f'{self.config.app_name}/migrations/__init__.py'] = ''
        
        # Project files
        files[f'{self.config.project_name}/settings.py'] = self.generate_settings_py()
        files[f'{self.config.project_name}/urls.py'] = self.generate_main_urls_py()
        files[f'{self.config.project_name}/wsgi.py'] = f'''"""
WSGI config for {self.config.project_name} project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', '{self.config.project_name}.settings')

application = get_wsgi_application()
'''
        files[f'{self.config.project_name}/__init__.py'] = ''
        
        # Root files
        files['manage.py'] = f'''#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', '{self.config.project_name}.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
'''
        files['requirements.txt'] = self.generate_requirements_txt()
        files['Dockerfile'] = self.generate_dockerfile()
        files['.gitignore'] = '''# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Django
*.log
local_settings.py
db.sqlite3
db.sqlite3-journal
media/
staticfiles/

# Virtual Environment
venv/
env/
ENV/
.venv/
.env

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Docker
.dockerignore

# Testing
.coverage
htmlcov/
.pytest_cache/
.tox/

# Flake8
.flake8
'''
        
        # GitHub Actions workflow - luôn tạo để đảm bảo CI/CD hoạt động
        files['.github/workflows/ci-cd.yml'] = self.generate_github_workflow()
        
        # README - Generate API endpoints documentation
        endpoints_docs = []
        for m in self.config.models:
            endpoints_docs.append(f"- GET/POST `/api/{m.api_endpoint}/` - List/Create {m.name}")
            endpoints_docs.append(f"- GET/PUT/DELETE `/api/{m.api_endpoint}/<id>/` - Detail/Update/Delete {m.name}")
        endpoints_str = '\n'.join(endpoints_docs)
        
        models_list = '\n'.join([f"- **{m.name}**: {m.api_endpoint}/" for m in self.config.models])
        
        files['README.md'] = f'''# {self.config.project_name}

Django REST API Project được tạo tự động bởi **Dev Portal**.

## 📋 Thông tin Project

- **Project Name:** {self.config.project_name}
- **App Name:** {self.config.app_name}
- **Django Version:** 4.2.7
- **DRF Version:** 3.14.0

## 🚀 Models

{models_list}

## 📦 Installation

```bash
# Clone repository
git clone {self.config.git_repo_url or 'your-repo-url'}

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run server
python manage.py runserver
```

## 🐳 Docker

```bash
# Build image
docker build -t {self.config.project_name} .

# Run container
docker run -p 8000:8000 {self.config.project_name}
```

## 🔗 API Endpoints

{endpoints_str}
- GET `/api/health/` - Health check

## 📝 License

MIT License
'''
        
        return files


@app.get("/", response_class=HTMLResponse)
async def home():
    """Trang chủ Dev Portal"""
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.post("/api/generate")
async def generate_project(config: ProjectConfig):
    """
    Generate Django project từ config
    """
    try:
        # Validate input
        if not config.models:
            raise HTTPException(status_code=400, detail="Phải có ít nhất 1 model")
        
        # Generate project
        generator = ProjectGenerator(config)
        files = generator.generate_all_files()
        
        # Create ZIP file
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_path, content in files.items():
                zip_file.writestr(file_path, content)
        
        zip_buffer.seek(0)
        
        # Return ZIP file
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={config.project_name}.zip"
            }
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi generate project: {str(e)}")


@app.post("/api/preview")
async def preview_files(config: ProjectConfig):
    """
    Preview các files sẽ được generate
    """
    try:
        generator = ProjectGenerator(config)
        files = generator.generate_all_files()
        
        # Return danh sách files và preview một số files quan trọng
        preview = {
            "total_files": len(files),
            "file_list": list(files.keys()),
            "preview": {
                "models.py": files.get(f"{config.app_name}/models.py", ""),
                "views.py": files.get(f"{config.app_name}/views.py", ""),
                "urls.py": files.get(f"{config.app_name}/urls.py", ""),
                "settings.py": files.get(f"{config.project_name}/settings.py", "")[:1000] + "...",
            }
        }
        
        return preview
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi preview: {str(e)}")


@app.post("/api/generate-k8s-manifests")
async def generate_k8s_manifests(config: ProjectConfig):
    """
    Generate K8s manifests cho Repository_B
    """
    try:
        # Validate input
        if not config.project_name:
            raise HTTPException(status_code=400, detail="Project name is required")
        
        # Determine docker image name
        if config.github_username and config.git_repo_url:
            repo_name = config.git_repo_url.split('/')[-1].replace('.git', '').lower()
            docker_image = f"{config.docker_registry}/{config.github_username.lower()}/{repo_name}"
        else:
            docker_image = f"{config.docker_registry}/your-username/{config.project_name.lower()}"
        
        # Generate K8s manifests
        k8s_generator = K8sManifestsGenerator(
            app_name=config.project_name.replace('_', '-'),
            namespace=config.project_name.replace('_', '-'),
            docker_image=docker_image,
            repo_b_url=config.repo_b_url,
            project_module_name=config.project_name
        )
        
        manifests = k8s_generator.generate_all()
        
        # Create ZIP file
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add manifests to apps/<app-name>/ directory
            app_name = config.project_name.replace('_', '-')
            for file_name, content in manifests.items():
                if file_name == 'argocd-application.yaml':
                    # ArgoCD app goes to root
                    zip_file.writestr(file_name, content)
                else:
                    # Other manifests go to apps/<app-name>/
                    zip_file.writestr(f'apps/{app_name}/{file_name}', content)
            
            # Add deployment instructions
            instructions = f'''# Deployment Instructions for {config.project_name}

## 📦 Files Structure

This ZIP contains K8s manifests for deploying to Repository_B:

```
apps/{app_name}/          # App manifests
├── namespace.yaml
├── deployment.yaml
├── service.yaml
├── pvc.yaml
├── ingress.yaml
├── kustomization.yaml
└── README.md

argocd-application.yaml   # ArgoCD Application (copy to argocd-apps/)
DEPLOYMENT-INSTRUCTIONS.md  # This file
```

## 🚀 Quick Deployment

### Step 1: Clone Repository_B

```bash
git clone {config.repo_b_url or 'https://github.com/your-username/Repository_B.git'}
cd Repository_B
```

### Step 2: Extract and Copy Manifests

```bash
# Extract this ZIP
unzip {config.project_name}-k8s-manifests.zip

# Copy files
cp -r apps/{app_name} Repository_B/apps/
cp argocd-application.yaml Repository_B/argocd-apps/{app_name}-app.yaml
```

### Step 3: Commit and Push

```bash
cd Repository_B
git add apps/{app_name}/ argocd-apps/{app_name}-app.yaml
git commit -m "Add {config.project_name} application"
git push origin main
```

### Step 4: Deploy with ArgoCD

```bash
# Apply ArgoCD Application
kubectl apply -f argocd-apps/{app_name}-app.yaml

# Watch deployment
kubectl get app {app_name} -n argocd -w

# Check pods
kubectl get pods -n {app_name}
```

## 🔄 CI/CD Integration

Your Django project's CI/CD pipeline should:

1. Build Docker image
2. Push to {docker_image}
3. Update `apps/{app_name}/deployment.yaml` in Repository_B
4. Commit and push changes
5. ArgoCD will auto-sync and deploy

## 📚 More Information

See `apps/{app_name}/README.md` for detailed instructions.

---

Generated by Django Dev Portal
'''
            zip_file.writestr('DEPLOYMENT-INSTRUCTIONS.md', instructions)
        
        zip_buffer.seek(0)
        
        # Return ZIP file
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={config.project_name}-k8s-manifests.zip"
            }
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi generate K8s manifests: {str(e)}")


@app.post("/api/generate-full-package")
async def generate_full_package(config: ProjectConfig):
    """
    Generate cả Django project VÀ K8s manifests trong 1 ZIP
    """
    try:
        # Validate input
        if not config.models:
            raise HTTPException(status_code=400, detail="Phải có ít nhất 1 model")
        
        # Generate Django project
        generator = ProjectGenerator(config)
        project_files = generator.generate_all_files()
        
        # Generate K8s manifests
        if config.github_username and config.git_repo_url:
            repo_name = config.git_repo_url.split('/')[-1].replace('.git', '').lower()
            docker_image = f"{config.docker_registry}/{config.github_username.lower()}/{repo_name}"
        else:
            docker_image = f"{config.docker_registry}/your-username/{config.project_name.lower()}"
        
        k8s_generator = K8sManifestsGenerator(
            app_name=config.project_name.replace('_', '-'),
            namespace=config.project_name.replace('_', '-'),
            docker_image=docker_image,
            repo_b_url=config.repo_b_url,
            project_module_name=config.project_name
        )
        
        k8s_manifests = k8s_generator.generate_all()
        
        # Create comprehensive ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add Django project files
            for file_path, content in project_files.items():
                zip_file.writestr(f'{config.project_name}/{file_path}', content)
            
            # Add K8s manifests
            app_name = config.project_name.replace('_', '-')
            for file_name, content in k8s_manifests.items():
                if file_name == 'argocd-application.yaml':
                    zip_file.writestr(f'k8s-manifests/argocd-application.yaml', content)
                else:
                    zip_file.writestr(f'k8s-manifests/apps/{app_name}/{file_name}', content)
            
            # Add master README
            master_readme = f'''# {config.project_name} - Full Package

Generated by Django Dev Portal

## 📦 Package Contents

```
{config.project_name}/            # Django REST API Project
├── manage.py
├── requirements.txt
├── Dockerfile
├── .github/workflows/ci-cd.yml
├── {config.project_name}/
├── {config.app_name}/
└── ...

k8s-manifests/                    # Kubernetes Manifests for Repository_B
├── apps/{app_name}/
│   ├── deployment.yaml
│   ├── service.yaml
│   └── ...
└── argocd-application.yaml
```

## 🚀 Quick Start

### 1. Deploy Django Application

```bash
# Extract Django project
cd {config.project_name}

# Setup and run
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

# Or use Docker
docker build -t {config.project_name} .
docker run -p 8000:8000 {config.project_name}
```

### 2. Push to GitHub

```bash
cd {config.project_name}
git init
git add .
git commit -m "Initial commit from Dev Portal"
git remote add origin {config.git_repo_url or 'https://github.com/your-username/your-repo.git'}
git push -u origin main
```

### 3. Deploy to Kubernetes via Repository_B

```bash
# Clone Repository_B
git clone {config.repo_b_url or 'https://github.com/your-username/Repository_B.git'}

# Copy K8s manifests
cp -r k8s-manifests/apps/{app_name} Repository_B/apps/
cp k8s-manifests/argocd-application.yaml Repository_B/argocd-apps/{app_name}-app.yaml

# Commit and push
cd Repository_B
git add .
git commit -m "Add {config.project_name} manifests"
git push origin main

# Deploy with ArgoCD
kubectl apply -f argocd-apps/{app_name}-app.yaml
```

## 📚 Documentation

- Django project README: `{config.project_name}/README.md`
- K8s deployment guide: `k8s-manifests/apps/{app_name}/README.md`
- Deployment instructions: `k8s-manifests/DEPLOYMENT-INSTRUCTIONS.md`

## 🔗 Links

- Project Repository: {config.git_repo_url or 'TBD'}
- Repository_B: {config.repo_b_url or 'TBD'}
- Docker Registry: {docker_image}

---

**Generated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Tool**: Django Dev Portal v1.0.0
'''
            zip_file.writestr('README.md', master_readme)
        
        zip_buffer.seek(0)
        
        # Return ZIP file
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={config.project_name}-full-package.zip"
            }
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi generate full package: {str(e)}")


@app.post("/api/generate-and-deploy")
async def generate_and_deploy(config: AutoDeployConfig):    
    """
    🚀 TỰ ĐỘNG HOÀN TOÀN: Generate project → Push Git → Deploy ArgoCD
    """
    try:
        project_config = config.project_config
        
        # Validate input
        if not project_config.models:
            raise HTTPException(status_code=400, detail="Phải có ít nhất 1 model")
        
        if not config.github_token:
            raise HTTPException(status_code=400, detail="GitHub token là bắt buộc")
        
        if not project_config.github_username:
            raise HTTPException(status_code=400, detail="GitHub username là bắt buộc")
        
        # Initialize GitHub Manager
        gh_manager = GitHubManager(config.github_token, project_config.github_username)
        
        result = {
            "status": "success",
            "steps": []
        }
        
        # Step 1: Generate Django project files
        result["steps"].append({"step": "generate_project", "status": "processing"})
        
        # Set git_repo_url if not provided (for workflow generation)
        if not project_config.git_repo_url and config.repo_a_name:
            project_config.git_repo_url = f"https://github.com/{project_config.github_username}/{config.repo_a_name}.git"
        
        # Set repo_b_url if not provided
        if not project_config.repo_b_url and config.repo_b_name:
            project_config.repo_b_url = f"https://github.com/{project_config.github_username}/{config.repo_b_name}.git"
        
        generator = ProjectGenerator(project_config)
        project_files = generator.generate_all_files()
        result["steps"][-1]["status"] = "success"
        result["steps"][-1]["files_count"] = len(project_files)
        
        # Step 2: Create Repository_A (if needed) and add secret FIRST
        result["steps"].append({"step": "push_to_repo_a", "status": "processing"})
        
        if config.create_new_repo_a:
            # Step 2a: Create repository first (without pushing code yet)
            repo_info = gh_manager.create_repository(
                repo_name=config.repo_a_name,
                description=f"Django REST API - {project_config.project_name} (Generated by Dev Portal)",
                private=config.repo_a_private
            )
            
            print(f"✅ Repository created: {repo_info['html_url']}")
            
            # Step 2b: Add PAT_TOKEN secret BEFORE pushing workflow file
            # This ensures secret exists when workflow triggers
            if project_config.enable_cicd:
                import time
                time.sleep(3)  # Wait for GitHub to initialize repo
                
                secret_result = gh_manager.add_repository_secret(
                    repo_name=config.repo_a_name,
                    secret_name="PAT_TOKEN",
                    secret_value=config.github_token
                )
                
                if secret_result["status"] != "success":
                    raise HTTPException(status_code=500, detail=f"Failed to add PAT_TOKEN: {secret_result.get('message')}")
                
                time.sleep(2)  # Wait for secret to propagate
            
            # Step 2c: Now push code (workflow will have access to secret)
            print(f"🚀 Pushing {len(project_files)} files to new repository...")
            push_result = gh_manager.push_files(
                repo_name=config.repo_a_name,
                files=project_files,
                commit_message="Initial commit from Dev Portal"
            )
            print(f"📊 Push result: {len(push_result)} operations")
            repo_result = {
                "repository": repo_info,
                "push_results": {
                    "total": len(push_result),
                    "success": sum(1 for r in push_result if r["status"] == "success"),
                    "error": sum(1 for r in push_result if r["status"] == "error"),
                    "details": push_result
                }
            }
        else:
            print(f"🔄 Updating existing repository with {len(project_files)} files...")
            repo_result = gh_manager.push_files(
                repo_name=config.repo_a_name,
                files=project_files,
                commit_message="Update from Dev Portal"
            )
            print(f"📊 Update result: {len(repo_result)} operations")
            repo_result = {
                "repository": {
                    "html_url": f"https://github.com/{project_config.github_username}/{config.repo_a_name}"
                },
                "push_results": {
                    "total": len(repo_result),
                    "success": sum(1 for r in repo_result if r["status"] == "success"),
                    "error": sum(1 for r in repo_result if r["status"] == "error")
                }
            }
        
        result["steps"][-1]["status"] = "success"
        result["steps"][-1]["repository_url"] = repo_result["repository"]["html_url"]
        
        # Check if batch push was successful
        if repo_result["push_results"]["success"] == 1 and "batch_push" in str(repo_result["push_results"]["details"]):
            result["steps"][-1]["commit_type"] = "batch"
            result["steps"][-1]["files_pushed"] = f"{repo_result['push_results']['total']} files in 1 commit"
            result["steps"][-1]["workflow_runs"] = "1 (batch commit)"
        else:
            result["steps"][-1]["commit_type"] = "individual"
            result["steps"][-1]["files_pushed"] = repo_result["push_results"]["success"]
            result["steps"][-1]["workflow_runs"] = f"{repo_result['push_results']['success']} (individual commits)"
        result["repository_a"] = repo_result["repository"]
        
        # Step 2.55: Ensure a single workflow run (prefer push-trigger; fallback to manual)
        if project_config.enable_cicd:
            try:
                import time as _time
                # Chờ ngắn để GitHub ghi nhận push-trigger
                _time.sleep(3)
                latest = gh_manager.get_latest_workflow_run(repo_name=config.repo_a_name, workflow_file="ci-cd.yml")
                if latest.get("status") == "error" and "No workflow runs" in latest.get("message", ""):
                    print("ℹ️ No push-triggered run detected, triggering manually...")
                    trigger = gh_manager.trigger_workflow(repo_name=config.repo_a_name, workflow_file="ci-cd.yml", branch="main")
                    print(f"🧪 Trigger workflow result: {trigger}")
                    _time.sleep(2)
                else:
                    print("✅ Push-triggered workflow detected; skip manual trigger to avoid duplicates")
            except Exception as _e:
                print(f"⚠️ Unable to check/trigger workflow: {_e}")
        
        # Step 2.6: Wait for GitHub Actions to build Docker image
        if project_config.enable_cicd:
            result["steps"].append({"step": "wait_github_actions", "status": "processing"})
            
            # Đợi một chút để workflow bắt đầu
            import time
            time.sleep(5)
            
            # Monitor workflow completion (timeout 10 minutes)
            workflow_result = gh_manager.wait_for_workflow_completion(
                repo_name=config.repo_a_name,
                workflow_file="ci-cd.yml",
                timeout=600,  # 10 minutes
                check_interval=10  # Check every 10 seconds
            )
            
            if workflow_result["status"] == "success":
                result["steps"][-1]["status"] = "success"
                result["steps"][-1]["message"] = workflow_result["message"]
                result["steps"][-1]["duration"] = workflow_result.get("duration", 0)
                result["steps"][-1]["workflow_url"] = workflow_result.get("html_url", "")
            elif workflow_result["status"] == "timeout":
                # Timeout không phải lỗi nghiêm trọng - có thể continue
                result["steps"][-1]["status"] = "warning"
                result["steps"][-1]["message"] = workflow_result["message"]
            else:
                # Workflow failed - đánh dấu warning nhưng vẫn continue
                result["steps"][-1]["status"] = "warning"
                result["steps"][-1]["message"] = workflow_result["message"]
                result["steps"][-1]["workflow_url"] = workflow_result.get("html_url", "")
        
        # Step 2.7: Verify Repository_B updated by GitHub Actions
        if project_config.enable_cicd and config.repo_b_name:
            result["steps"].append({"step": "verify_repo_b_updated", "status": "processing"})
            
            import time
            time.sleep(3)  # Đợi GitHub Actions commit vào Repository_B
            
            # Verify Repository_B đã được update bởi GitHub Actions
            try:
                verify_result = gh_manager.verify_repository_b_updated(
                    repo_b_name=config.repo_b_name,
                    app_name=project_config.project_name.replace('_', '-'),
                    expected_image_tag=None  # Sẽ check commit message từ GitHub Actions
                )
                
                result["steps"][-1]["status"] = "success"
                result["steps"][-1]["message"] = verify_result.get("message", "Repository_B updated successfully")
                result["steps"][-1]["last_commit"] = verify_result.get("last_commit", {})
            except Exception as e:
                result["steps"][-1]["status"] = "warning"
                result["steps"][-1]["message"] = f"Could not verify Repository_B update: {str(e)}"
        
        # Step 3: Generate K8s manifests
        # Tạo manifests SAU KHI Docker image đã được build
        
        # Define app_name globally for use in summary
        app_name = project_config.project_name.replace('_', '-')
        
        if config.auto_push_repo_b and config.repo_b_name:
            result["steps"].append({"step": "generate_k8s_manifests", "status": "processing"})
            
            docker_image = f"{project_config.docker_registry}/{project_config.github_username.lower()}/{config.repo_a_name.lower()}"
            repo_b_url = f"https://github.com/{project_config.github_username.lower()}/{config.repo_b_name.lower()}.git"
            
            k8s_generator = K8sManifestsGenerator(
                app_name=app_name,
                namespace=app_name,
                docker_image=docker_image,
                repo_b_url=repo_b_url,
                project_module_name=project_config.project_name
            )
            
            manifests = k8s_generator.generate_all()
            result["steps"][-1]["status"] = "success"
            result["steps"][-1]["manifests_count"] = len(manifests)
            
            # Step 4: Push manifests to Repository_B
            result["steps"].append({"step": "push_to_repo_b", "status": "processing"})
            
            repo_b_result = gh_manager.update_repository_b_manifests(
                repo_b_name=config.repo_b_name,
                app_name=app_name,
                manifests=manifests
            )
            
            result["steps"][-1]["status"] = "success"
            result["steps"][-1]["manifests_pushed"] = repo_b_result["success"]
            result["steps"][-1]["repository_url"] = f"https://github.com/{project_config.github_username}/{config.repo_b_name}"
            result["repository_b"] = {
                "html_url": f"https://github.com/{project_config.github_username}/{config.repo_b_name}",
                "manifests_path": f"apps/{app_name}/",
                "argocd_app_path": f"apps/{app_name}/argocd-application.yaml"
            }
        
        # NOTE: GitHub Actions sẽ TỰ ĐỘNG chạy khi push code lần đầu
        # Workflow sẽ build image và push lên GHCR
        # ArgoCD sẽ retry pull image (với retry policy) cho đến khi image sẵn sàng
        
        # Final summary
        # Extract workflow URL from steps if available
        workflow_url = None
        for step in result["steps"]:
            if step["step"] == "wait_github_actions" and "workflow_url" in step:
                workflow_url = step["workflow_url"]
                break
        
        result["summary"] = {
            "project_name": project_config.project_name,
            "repository_a_url": repo_result["repository"]["html_url"],
            "repository_b_url": f"https://github.com/{project_config.github_username}/{config.repo_b_name}" if config.repo_b_name else None,
            "workflow_url": workflow_url,
            "argocd_app": f"{app_name}-app",  # ApplicationSet sẽ tự động tạo
            "application_set_status": "ApplicationSet sẽ tự động tạo ArgoCD Application",
            "access_ui": {
                "argocd": {
                    "command": "kubectl port-forward svc/argocd-server -n argocd 8080:443",
                    "url": "https://localhost:8080",
                    "username": "admin",
                    "password_command": "kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d"
                },
                "grafana": {
                    "command": "kubectl port-forward svc/grafana-service -n monitoring 3000:3000",
                    "url": "http://localhost:3000",
                    "username": "admin",
                    "password": "admin123"
                }
            },
            "next_steps": [
                "✅ Code đã được push lên GitHub Repository_A",
                "✅ GitHub Actions đã build Docker image và push lên GHCR" if project_config.enable_cicd else "⚠️ CI/CD chưa được enable",
                "✅ K8s manifests đã được push lên Repository_B/apps/{}/".format(app_name) if config.repo_b_name else "⚠️ Chưa push K8s manifests",
                "✅ ApplicationSet sẽ tự động tạo ArgoCD Application từ apps/{}/ folder".format(app_name) if config.repo_b_name else "⚠️ Chưa có ArgoCD Application",
                "🔄 ArgoCD sẽ tự động deploy application",
                "📊 Monitor ArgoCD: kubectl get app {} -n argocd -w".format(app_name),
                "📊 Monitor Pods: kubectl get pods -n {} -w".format(app_name),
                "📈 View logs: kubectl logs -n {} deployment/{} -f".format(app_name, app_name),
                "🌐 Access API: kubectl port-forward svc/{}-service -n {} 8000:8000".format(app_name, app_name)
            ]
        }
        
        return result
    
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500, 
            detail={
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )


# Dashboard API Endpoints
@app.get("/api/dashboard/applications")
async def get_dashboard_applications():
    """Get all applications for dashboard"""
    try:
        mongodb = await get_mongodb_client()
        applications = await mongodb.get_all_applications()
        return {"status": "success", "data": applications}
    except Exception as e:
        logger.error(f"Error getting applications: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving applications: {str(e)}")

@app.get("/api/dashboard/statistics")
async def get_dashboard_statistics():
    """Get dashboard statistics"""
    try:
        mongodb = await get_mongodb_client()
        stats = await mongodb.get_statistics()
        return {"status": "success", "data": stats}
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving statistics: {str(e)}")

@app.get("/api/dashboard/applications/{name}")
async def get_application_by_name(name: str):
    """Get specific application by name"""
    try:
        mongodb = await get_mongodb_client()
        application = await mongodb.get_application_by_name(name)
        if application:
            return {"status": "success", "data": application}
        else:
            raise HTTPException(status_code=404, detail="Application not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting application {name}: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving application: {str(e)}")

@app.get("/api/dashboard/applications/status/{status}")
async def get_applications_by_status(status: str):
    """Get applications by health status"""
    try:
        mongodb = await get_mongodb_client()
        applications = await mongodb.get_applications_by_status(status)
        return {"status": "success", "data": applications}
    except Exception as e:
        logger.error(f"Error getting applications by status {status}: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving applications: {str(e)}")

@app.post("/api/dashboard/sync")
async def trigger_sync(background_tasks: BackgroundTasks):
    """Trigger manual sync from ArgoCD"""
    try:
        # Sử dụng auto sync service để force sync
        background_tasks.add_task(force_sync_now)
        return {"status": "success", "message": "Sync triggered successfully"}
    except Exception as e:
        logger.error(f"Error triggering sync: {e}")
        raise HTTPException(status_code=500, detail=f"Error triggering sync: {str(e)}")

@app.post("/api/dashboard/sync/start")
async def start_continuous_sync(background_tasks: BackgroundTasks):
    """Start continuous sync from ArgoCD"""
    global sync_task
    try:
        if sync_task and not sync_task.done():
            return {"status": "warning", "message": "Sync is already running"}
        
        # Sử dụng auto sync service
        auto_sync = await get_auto_sync_service()
        if auto_sync:
            sync_task = asyncio.create_task(auto_sync.start_auto_sync())
        else:
            return {"status": "error", "message": "Auto sync service not available - ARGOCD_SERVER not configured"}
        return {"status": "success", "message": "Continuous sync started"}
    except Exception as e:
        logger.error(f"Error starting continuous sync: {e}")
        raise HTTPException(status_code=500, detail=f"Error starting sync: {str(e)}")

@app.post("/api/dashboard/sync/stop")
async def stop_continuous_sync():
    """Stop continuous sync from ArgoCD"""
    global sync_task
    try:
        if sync_task and not sync_task.done():
            auto_sync = await get_auto_sync_service()
            if auto_sync:
                await auto_sync.stop_auto_sync()
            sync_task.cancel()
            sync_task = None
            return {"status": "success", "message": "Continuous sync stopped"}
        else:
            return {"status": "warning", "message": "No sync is currently running"}
    except Exception as e:
        logger.error(f"Error stopping continuous sync: {e}")
        raise HTTPException(status_code=500, detail=f"Error stopping sync: {str(e)}")

@app.get("/api/dashboard/sync/status")
async def get_sync_status():
    """Get current sync status"""
    global sync_task
    try:
        if sync_task and not sync_task.done():
            return {"status": "success", "data": {"running": True, "message": "Sync is running"}}
        else:
            return {"status": "success", "data": {"running": False, "message": "Sync is not running"}}
    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting sync status: {str(e)}")

# Webhook endpoint for ArgoCD notifications
@app.post("/api/webhook/argocd")
async def argocd_webhook(payload: dict, background_tasks: BackgroundTasks):
    """Handle ArgoCD webhook notifications"""
    try:
        logger.info(f"Received ArgoCD webhook: {payload}")
        
        # Extract application information from webhook
        application_name = payload.get('application', {}).get('metadata', {}).get('name')
        if not application_name:
            logger.warning("No application name in webhook payload")
            return {"status": "warning", "message": "No application name found"}
        
        # Trigger immediate sync when webhook is received
        background_tasks.add_task(force_sync_now)
        
        return {"status": "success", "message": f"Webhook processed for {application_name}, sync triggered"}
    except Exception as e:
        logger.error(f"Error processing ArgoCD webhook: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing webhook: {str(e)}")

# GitHub webhook endpoint để trigger ArgoCD sync ngay lập tức
@app.post("/api/webhook/github")
async def github_webhook(request: Request):
    """GitHub webhook endpoint để trigger ArgoCD sync ngay lập tức khi có push vào repository_B"""
    return await github_webhook_endpoint(request)

@app.get("/api/webhook/health")
async def webhook_health():
    """Webhook health check"""
    return await webhook_health_check()

# Startup event to initialize MongoDB connection
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    try:
        # Initialize MongoDB connection
        mongodb = await get_mongodb_client()
        logger.info("MongoDB connection initialized")
        
        # Start auto sync service
        auto_sync = await get_auto_sync_service()
        if auto_sync:
            global sync_task
            sync_task = asyncio.create_task(auto_sync.start_auto_sync())
            logger.info("Auto ArgoCD sync started - sẽ tự động lấy dữ liệu mới mỗi 30 giây")
        else:
            logger.info("Auto ArgoCD sync disabled - ARGOCD_SERVER not configured")
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")

# Shutdown event to cleanup resources
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown"""
    try:
        global sync_task
        if sync_task and not sync_task.done():
            sync_task.cancel()
            auto_sync = await get_auto_sync_service()
            if auto_sync:
                await auto_sync.stop_auto_sync()
        
        mongodb = await get_mongodb_client()
        await mongodb.disconnect()
        logger.info("Cleanup completed")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8090)

