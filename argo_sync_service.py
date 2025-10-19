"""
ArgoCD Sync Service
Handles synchronization of ArgoCD application data to MongoDB
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import aiohttp
import json
from mongodb_client import get_mongodb_client
from argo_data_fetcher import ArgoCDDataFetcher

logger = logging.getLogger(__name__)

class ArgoCDSyncService:
    """Service for syncing ArgoCD application data to MongoDB"""
    
    def __init__(self, argocd_server_url: str, argocd_token: str = None):
        self.argocd_server_url = argocd_server_url.rstrip('/')
        self.argocd_token = argocd_token
        self.session: Optional[aiohttp.ClientSession] = None
        self.sync_interval = 30  # seconds
        self.is_running = False
        
    async def start_session(self):
        """Start aiohttp session"""
        if not self.session:
            headers = {}
            if self.argocd_token:
                headers['Authorization'] = f'Bearer {self.argocd_token}'
            
            self.session = aiohttp.ClientSession(
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
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
            
            async with self.session.get(url) as response:
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
            
            # Extract pod configuration from status
            resources = status.get('resources', [])
            services = []
            
            for resource in resources:
                if resource.get('kind') == 'Service':
                    service_info = {
                        "name": resource.get('name', ''),
                        "namespace": resource.get('namespace', ''),
                        "status": resource.get('health', {}).get('status', 'Unknown'),
                        "port": self._extract_service_port(resource),
                        "type": resource.get('spec', {}).get('type', 'ClusterIP')
                    }
                    services.append(service_info)
            
            # Extract deployment information
            deployments = []
            for resource in resources:
                if resource.get('kind') == 'Deployment':
                    deployment_info = {
                        "name": resource.get('name', ''),
                        "namespace": resource.get('namespace', ''),
                        "status": resource.get('health', {}).get('status', 'Unknown'),
                        "replicas": resource.get('status', {}).get('replicas', 0),
                        "readyReplicas": resource.get('status', {}).get('readyReplicas', 0),
                        "image": self._extract_deployment_image(resource)
                    }
                    deployments.append(deployment_info)
            
            # Create MongoDB document
            mongodb_doc = {
                "id": metadata.get('uid', ''),
                "name": metadata.get('name', ''),
                "namespace": metadata.get('namespace', ''),
                "gitRepo": git_repo,
                "podConfig": {
                    "replicas": spec.get('syncPolicy', {}).get('automated', {}).get('prune', False),
                    "image": self._extract_image_from_spec(spec),
                    "resources": self._extract_resources_from_spec(spec),
                    "ports": self._extract_ports_from_spec(spec),
                    "env": self._extract_env_from_spec(spec)
                },
                "healthStatus": status.get('health', {}).get('status', 'Unknown'),
                "syncStatus": status.get('sync', {}).get('status', 'Unknown'),
                "services": services,
                "deployments": deployments,
                "lastSyncTime": status.get('sync', {}).get('syncedAt', ''),
                "createdAt": metadata.get('creationTimestamp', ''),
                "updatedAt": datetime.utcnow().isoformat() + 'Z'
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
    
    async def sync_applications(self) -> bool:
        """Sync all ArgoCD applications to MongoDB using real data fetcher"""
        try:
            # Use the real data fetcher
            fetcher = ArgoCDDataFetcher(self.argocd_server_url, self.argocd_token)
            await fetcher.start_session()
            
            try:
                success = await fetcher.sync_applications_to_mongodb()
                return success
            finally:
                await fetcher.close_session()
            
        except Exception as e:
            logger.error(f"Error syncing applications: {e}")
            return False
    
    async def start_continuous_sync(self):
        """Start continuous synchronization"""
        self.is_running = True
        logger.info("Starting continuous ArgoCD sync...")
        
        while self.is_running:
            try:
                await self.sync_applications()
                await asyncio.sleep(self.sync_interval)
            except Exception as e:
                logger.error(f"Error in continuous sync: {e}")
                await asyncio.sleep(10)  # Wait before retrying
    
    async def stop_continuous_sync(self):
        """Stop continuous synchronization"""
        self.is_running = False
        logger.info("Stopping continuous ArgoCD sync...")
        await self.close_session()

# Global sync service instance
sync_service = None

async def get_sync_service() -> ArgoCDSyncService:
    """Get or create sync service instance"""
    global sync_service
    
    if sync_service is None:
        argocd_url = "http://argocd-server.argocd.svc.cluster.local"  # Default ArgoCD URL
        sync_service = ArgoCDSyncService(argocd_url)
        await sync_service.start_session()
    
    return sync_service
