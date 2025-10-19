"""
Import existing services from Repository_B into MongoDB
Scan deployment.yaml files and create service metadata
"""
import yaml
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import os
import re

# MongoDB Connection
MONGODB_URL = "mongodb+srv://quandeptrai5122004_db_user:9Azl4x9Yo4NNl6Xd@devportal0.e5vwt7y.mongodb.net/?retryWrites=true&w=majority&appName=devportal0"

# Repository_B path (adjust if needed)
REPO_B_PATH = "../Repository_B/apps"


async def parse_deployment_yaml(file_path):
    """Parse deployment.yaml and extract metadata"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            deployment = yaml.safe_load(f)
        
        metadata = deployment.get('metadata', {})
        spec = deployment.get('spec', {})
        template = spec.get('template', {})
        container = template.get('spec', {}).get('containers', [{}])[0]
        
        # Extract basic info
        service_name = metadata.get('name', '')
        namespace = metadata.get('namespace', '')
        
        # Extract image
        docker_image = container.get('image', '').split(':')[0]  # Remove tag
        
        # Extract resources
        resources = container.get('resources', {})
        requests = resources.get('requests', {})
        limits = resources.get('limits', {})
        
        # Extract probes
        liveness_probe = container.get('livenessProbe', {})
        readiness_probe = container.get('readinessProbe', {})
        
        # Extract port
        ports = container.get('ports', [{}])
        port = ports[0].get('containerPort', 8000) if ports else 8000
        
        # Extract volume info
        volumes = template.get('spec', {}).get('volumes', [])
        pvc_name = None
        for vol in volumes:
            pvc = vol.get('persistentVolumeClaim', {})
            if pvc:
                pvc_name = pvc.get('claimName', '')
                break
        
        k8s_config = {
            'memory_request': requests.get('memory', '256Mi'),
            'memory_limit': limits.get('memory', '512Mi'),
            'cpu_request': requests.get('cpu', '250m'),
            'cpu_limit': limits.get('cpu', '500m'),
            'replicas': spec.get('replicas', 2),
            'port': port,
            'pvc_size': '1Gi',  # Default, can't extract from deployment
            'storage_class': 'standard',  # Default
            'domain': None,
            'enable_tls': True,
            'liveness_initial_delay': liveness_probe.get('initialDelaySeconds', 30),
            'readiness_initial_delay': readiness_probe.get('initialDelaySeconds', 5)
        }
        
        # Extract project module name from env or command
        env_vars = container.get('env', [])
        project_module = None
        for env in env_vars:
            if env.get('name') == 'DJANGO_SETTINGS_MODULE':
                value = env.get('value', '')
                project_module = value.split('.')[0] if '.' in value else None
                break
        
        # Try to extract from args
        if not project_module:
            args = container.get('args', [])
            if args and isinstance(args[0], str):
                match = re.search(r'gunicorn.*?(\w+)\.wsgi', args[0])
                if match:
                    project_module = match.group(1)
        
        return {
            'service_name': service_name,
            'namespace': namespace,
            'docker_image': docker_image,
            'k8s_config': k8s_config,
            'project_module': project_module or service_name.replace('-', '_')
        }
    
    except Exception as e:
        print(f"Error parsing {file_path}: {str(e)}")
        return None


async def import_services():
    """Import all existing services from Repository_B"""
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client.devportal
    services_collection = db.services
    
    print("🔍 Scanning Repository_B for existing services...")
    
    # Scan apps directory
    apps_dirs = []
    try:
        apps_dirs = [d for d in os.listdir(REPO_B_PATH) 
                     if os.path.isdir(os.path.join(REPO_B_PATH, d))]
    except FileNotFoundError:
        print(f"❌ Repository_B path not found: {REPO_B_PATH}")
        print("💡 Please adjust REPO_B_PATH in the script")
        return
    
    print(f"📁 Found {len(apps_dirs)} apps: {', '.join(apps_dirs)}")
    
    imported = 0
    skipped = 0
    
    for app_dir in apps_dirs:
        deployment_path = os.path.join(REPO_B_PATH, app_dir, 'deployment.yaml')
        
        if not os.path.exists(deployment_path):
            print(f"⚠️  Skipping {app_dir}: No deployment.yaml")
            skipped += 1
            continue
        
        # Parse deployment
        service_data = await parse_deployment_yaml(deployment_path)
        
        if not service_data:
            skipped += 1
            continue
        
        # Check if already exists
        existing = await services_collection.find_one({
            'service_name': service_data['service_name']
        })
        
        if existing:
            print(f"⏭️  Skipping {service_data['service_name']}: Already exists in database")
            skipped += 1
            continue
        
        # Create service metadata
        service_metadata = {
            'service_name': service_data['service_name'],
            'project_name': service_data['project_module'],
            'app_name': 'api',  # Default
            'namespace': service_data['namespace'],
            'docker_image': service_data['docker_image'],
            'repository_a_url': None,  # Unknown for existing services
            'repository_b_url': 'https://github.com/quanmbl4255142/Repository_B.git',
            'k8s_config': service_data['k8s_config'],
            'models': [],  # Unknown for existing services
            'status': 'running',  # Assume running
            'health_status': 'unknown',
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'last_deployed': None,
            'argocd_app_name': f"{service_data['service_name']}-app",
            'ingress_url': f"https://{service_data['service_name']}.yourdomain.com",
            'github_workflow_url': None,
            'error_message': None
        }
        
        # Insert to MongoDB
        await services_collection.insert_one(service_metadata)
        
        print(f"✅ Imported: {service_data['service_name']}")
        imported += 1
    
    print(f"\n📊 Summary:")
    print(f"   ✅ Imported: {imported}")
    print(f"   ⏭️  Skipped: {skipped}")
    print(f"   📝 Total: {len(apps_dirs)}")
    
    # Close connection
    client.close()
    print("\n🎉 Import complete! Check dashboard at http://localhost:8090/dashboard")


if __name__ == "__main__":
    asyncio.run(import_services())



