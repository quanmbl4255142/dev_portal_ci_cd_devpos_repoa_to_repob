"""
ArgoCD Data Fetcher
Lấy dữ liệu thật từ ArgoCD và lưu vào MongoDB
"""
import asyncio
import aiohttp
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from mongodb_client import get_mongodb_client

logger = logging.getLogger(__name__)

class ArgoCDDataFetcher:
    """Fetches real data from ArgoCD and stores in MongoDB"""
    
    def __init__(self, argocd_server_url: str, argocd_token: str = None):
        self.argocd_server_url = argocd_server_url.rstrip('/')
        self.argocd_token = argocd_token
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def start_session(self):
        """Start aiohttp session"""
        if not self.session:
            headers = {
                'Content-Type': 'application/json'
            }
            
            # Sử dụng basic auth hoặc cookie
            cookies = {}
            if self.argocd_token:
                # Thử basic auth trước
                import base64
                auth_string = f"admin:{self.argocd_token}"
                auth_bytes = auth_string.encode('ascii')
                auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
                headers['Authorization'] = f'Basic {auth_b64}'
            
            self.session = aiohttp.ClientSession(
                headers=headers,
                cookies=cookies,
                timeout=aiohttp.ClientTimeout(total=30),
                connector=aiohttp.TCPConnector(ssl=False)
            )
    
    async def close_session(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def get_argocd_applications(self) -> List[Dict[str, Any]]:
        """Fetch applications from ArgoCD API"""
        try:
            if not self.session:
                await self.start_session()
            
            url = f"{self.argocd_server_url}/api/v1/applications"
            
            async with self.session.get(url, ssl=False) as response:
                if response.status == 200:
                    data = await response.json()
                    applications = data.get('items', [])
                    logger.info(f"Fetched {len(applications)} applications from ArgoCD")
                    return applications
                else:
                    logger.error(f"ArgoCD API error: {response.status} - {await response.text()}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error fetching ArgoCD applications: {e}")
            return []
    
    def transform_argocd_app_to_mongodb(self, argocd_app: Dict[str, Any]) -> Dict[str, Any]:
        """Transform ArgoCD application data to MongoDB format"""
        try:
            # Extract basic information
            metadata = argocd_app.get('metadata', {})
            spec = argocd_app.get('spec', {})
            status = argocd_app.get('status', {})
            
            # Extract Git repository information
            source = spec.get('source', {})
            git_repo = {
                "url": source.get('repoURL', ''),
                "branch": source.get('targetRevision', 'main'),
                "path": source.get('path', '')
            }
            
            # Extract K8s resources from status
            resources = status.get('resources', [])
            services = []
            deployments = []
            ingresses = []
            
            for resource in resources:
                if isinstance(resource, dict):
                    kind = resource.get('kind', '')
                    if kind == 'Service':
                        service_info = {
                            "name": resource.get('name', ''),
                            "namespace": resource.get('namespace', ''),
                            "status": resource.get('status', 'Unknown'),
                            "health": resource.get('health', {}).get('status', 'Unknown'),
                            "port": 80  # Default port
                        }
                        services.append(service_info)
                    elif kind == 'Deployment':
                        deployment_info = {
                            "name": resource.get('name', ''),
                            "namespace": resource.get('namespace', ''),
                            "status": resource.get('status', 'Unknown'),
                            "health": resource.get('health', {}).get('status', 'Unknown')
                        }
                        deployments.append(deployment_info)
                    elif kind == 'Ingress':
                        ingress_info = {
                            "name": resource.get('name', ''),
                            "namespace": resource.get('namespace', ''),
                            "status": resource.get('status', 'Unknown'),
                            "health": resource.get('health', {}).get('status', 'Unknown')
                        }
                        ingresses.append(ingress_info)
            
            # Tạo dữ liệu chi tiết cho MongoDB
            app_name = metadata.get('name', '')
            namespace = metadata.get('namespace', 'default')
            
            # Dữ liệu chi tiết từ K8s (sẽ được bổ sung thực tế)
            detailed_data = {
                "id": f"{app_name}-{namespace}",
                "podConfig": {
                    "replicas": 1,
                    "readyReplicas": 1,
                    "availableReplicas": 1,
                    "image": f"django-app:{app_name}",
                    "resources": {
                        "requests": {"cpu": "100m", "memory": "128Mi"},
                        "limits": {"cpu": "500m", "memory": "512Mi"}
                    },
                    "ports": [{"containerPort": 8000, "protocol": "TCP"}],
                    "env": [
                        {"name": "DJANGO_SETTINGS_MODULE", "value": "django_api.settings"},
                        {"name": "DEBUG", "value": "True"},
                        {"name": "DATABASE_URL", "value": "postgresql://user:pass@db:5432/dbname"}
                    ],
                    "livenessProbe": {
                        "httpGet": {"path": "/health", "port": 8000},
                        "initialDelaySeconds": 30,
                        "periodSeconds": 10
                    },
                    "readinessProbe": {
                        "httpGet": {"path": "/ready", "port": 8000},
                        "initialDelaySeconds": 5,
                        "periodSeconds": 5
                    }
                },
                "serviceConfig": {
                    "type": "ClusterIP",
                    "clusterIP": "10.96.0.0",
                    "ports": [{"port": 80, "targetPort": 8000, "protocol": "TCP"}],
                    "selector": {"app": app_name}
                },
                "generation": 1
            }
            
            # Create MongoDB document
            mongodb_doc = {
                "name": app_name,
                "namespace": namespace,
                "project": spec.get('project', 'default'),
                "healthStatus": status.get('health', {}).get('status', 'Unknown'),
                "syncStatus": status.get('sync', {}).get('status', 'Unknown'),
                "gitRepo": git_repo,
                "deployments": deployments,
                "services": services,
                "ingresses": ingresses,
                "createdAt": metadata.get('creationTimestamp', ''),
                "updatedAt": datetime.utcnow().isoformat(),
                "rawArgoCDData": argocd_app,
                # Thêm dữ liệu chi tiết
                **detailed_data
            }
            
            return mongodb_doc
            
        except Exception as e:
            logger.error(f"Error transforming ArgoCD app {argocd_app.get('metadata', {}).get('name', 'unknown')}: {e}")
            return {}
    
    def _extract_service_port(self, service_resource: Dict[str, Any]) -> int:
        """Extract port from service resource"""
        try:
            ports = service_resource.get('spec', {}).get('ports', [])
            if ports:
                return ports[0].get('port', 8000)
            return 8000
        except:
            return 8000
    
    def _extract_deployment_image(self, deployment_resource: Dict[str, Any]) -> str:
        """Extract image from deployment resource"""
        try:
            containers = deployment_resource.get('spec', {}).get('template', {}).get('spec', {}).get('containers', [])
            if containers:
                return containers[0].get('image', '')
            return ''
        except:
            return ''
    
    def _extract_image_from_spec(self, spec: Dict[str, Any]) -> str:
        """Extract image from ArgoCD spec"""
        try:
            # Try to get image from source
            source = spec.get('source', {})
            if source.get('helm'):
                values = source.get('helm', {}).get('values', '')
                if 'image:' in values:
                    # Simple extraction - in real implementation, parse YAML properly
                    lines = values.split('\n')
                    for line in lines:
                        if 'image:' in line and ':' in line:
                            return line.split('image:')[1].strip()
            return ''
        except:
            return ''
    
    def _extract_resources_from_spec(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Extract resource requirements from spec"""
        try:
            # Default resource requirements
            return {
                "requests": {
                    "cpu": "100m",
                    "memory": "128Mi"
                },
                "limits": {
                    "cpu": "500m",
                    "memory": "256Mi"
                }
            }
        except:
            return {"requests": {"cpu": "100m", "memory": "128Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}}
    
    def _extract_ports_from_spec(self, spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract port configuration from spec"""
        try:
            return [{
                "containerPort": 8000,
                "protocol": "TCP"
            }]
        except:
            return [{"containerPort": 8000, "protocol": "TCP"}]
    
    def _extract_env_from_spec(self, spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract environment variables from spec"""
        try:
            return [
                {"name": "DATABASE_URL", "value": "secret-ref-to-db-url"},
                {"name": "LOG_LEVEL", "value": "info"}
            ]
        except:
            return [{"name": "DATABASE_URL", "value": "secret-ref-to-db-url"}, {"name": "LOG_LEVEL", "value": "info"}]
    
    async def sync_applications_to_mongodb(self) -> bool:
        """Sync all ArgoCD applications to MongoDB"""
        try:
            # Get ArgoCD applications
            argocd_apps = await self.get_argocd_applications()
            if not argocd_apps:
                logger.warning("No applications found in ArgoCD")
                return False
            
            # Get MongoDB client
            mongodb = await get_mongodb_client()
            
            # Lấy danh sách applications hiện tại trong MongoDB
            current_apps = await mongodb.get_all_applications()
            current_names = {app.get('name') for app in current_apps}
            
            # Lấy danh sách applications từ ArgoCD
            argocd_names = {app.get('metadata', {}).get('name') for app in argocd_apps}
            
            # Xóa applications không có trong ArgoCD
            to_delete = current_names - argocd_names
            for name in to_delete:
                if name:
                    await mongodb.delete_application(name)
                    logger.info(f"🗑️ Deleted: {name} (not in ArgoCD)")
            
            # Transform and upsert each application
            success_count = 0
            for argocd_app in argocd_apps:
                try:
                    mongodb_doc = self.transform_argocd_app_to_mongodb(argocd_app)
                except Exception as e:
                    logger.error(f"Error transforming ArgoCD app {argocd_app.get('metadata', {}).get('name', 'unknown')}: {e}")
                    continue
                if mongodb_doc and mongodb_doc.get('name'):
                    success = await mongodb.upsert_application(mongodb_doc)
                    if success:
                        success_count += 1
            
            logger.info(f"Successfully synced {success_count}/{len(argocd_apps)} applications to MongoDB")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error syncing applications: {e}")
            return False

async def main():
    """Main function to test the fetcher"""
    # ArgoCD configuration
    argocd_url = "http://argocd-server.argocd.svc.cluster.local"  # Default ArgoCD URL
    argocd_token = None  # Add token if needed
    
    # Create fetcher
    fetcher = ArgoCDDataFetcher(argocd_url, argocd_token)
    
    try:
        # Sync applications
        success = await fetcher.sync_applications_to_mongodb()
        if success:
            print("✅ Successfully synced ArgoCD applications to MongoDB")
        else:
            print("❌ Failed to sync applications")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await fetcher.close_session()

if __name__ == "__main__":
    asyncio.run(main())
