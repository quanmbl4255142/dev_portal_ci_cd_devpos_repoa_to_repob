#!/usr/bin/env python3
"""
Lấy dữ liệu chi tiết từ K8s API để bổ sung thông tin cho MongoDB
"""

import asyncio
import logging
import sys
import os
from typing import Dict, List, Any, Optional
import aiohttp
import base64

# Thêm thư mục hiện tại vào Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mongodb_client import get_mongodb_client

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class K8sDetailedFetcher:
    """Lấy dữ liệu chi tiết từ K8s API"""
    
    def __init__(self, k8s_api_url: str = "https://kubernetes.default.svc"):
        self.k8s_api_url = k8s_api_url
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def start_session(self):
        """Start aiohttp session với K8s API authentication"""
        if not self.session:
            # Lấy service account token
            token = await self._get_service_account_token()
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            self.session = aiohttp.ClientSession(
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
                connector=aiohttp.TCPConnector(ssl=False)
            )
    
    async def close_session(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def _get_service_account_token(self) -> str:
        """Lấy service account token từ K8s"""
        try:
            with open('/var/run/secrets/kubernetes.io/serviceaccount/token', 'r') as f:
                return f.read().strip()
        except:
            # Fallback token cho development
            return "fake-token"
    
    async def get_deployment_details(self, namespace: str, name: str) -> Dict[str, Any]:
        """Lấy chi tiết deployment từ K8s API"""
        try:
            if not self.session:
                await self.start_session()
            
            url = f"{self.k8s_api_url}/apis/apps/v1/namespaces/{namespace}/deployments/{name}"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._extract_deployment_details(data)
                else:
                    logger.warning(f"Failed to get deployment {name}: {response.status}")
                    return {}
        except Exception as e:
            logger.error(f"Error getting deployment details for {name}: {e}")
            return {}
    
    def _extract_deployment_details(self, deployment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract chi tiết từ deployment data"""
        try:
            spec = deployment_data.get('spec', {})
            status = deployment_data.get('status', {})
            metadata = deployment_data.get('metadata', {})
            
            # Lấy thông tin replicas
            replicas = spec.get('replicas', 0)
            ready_replicas = status.get('readyReplicas', 0)
            available_replicas = status.get('availableReplicas', 0)
            
            # Lấy thông tin container
            containers = spec.get('template', {}).get('spec', {}).get('containers', [])
            container_info = {}
            
            if containers:
                container = containers[0]  # Lấy container đầu tiên
                container_info = {
                    "name": container.get('name', ''),
                    "image": container.get('image', ''),
                    "ports": container.get('ports', []),
                    "env": container.get('env', []),
                    "resources": container.get('resources', {}),
                    "livenessProbe": container.get('livenessProbe', {}),
                    "readinessProbe": container.get('readinessProbe', {})
                }
            
            return {
                "replicas": replicas,
                "readyReplicas": ready_replicas,
                "availableReplicas": available_replicas,
                "container": container_info,
                "creationTimestamp": metadata.get('creationTimestamp', ''),
                "generation": metadata.get('generation', 0),
                "uid": metadata.get('uid', '')
            }
            
        except Exception as e:
            logger.error(f"Error extracting deployment details: {e}")
            return {}
    
    async def get_service_details(self, namespace: str, name: str) -> Dict[str, Any]:
        """Lấy chi tiết service từ K8s API"""
        try:
            if not self.session:
                await self.start_session()
            
            url = f"{self.k8s_api_url}/api/v1/namespaces/{namespace}/services/{name}"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._extract_service_details(data)
                else:
                    logger.warning(f"Failed to get service {name}: {response.status}")
                    return {}
        except Exception as e:
            logger.error(f"Error getting service details for {name}: {e}")
            return {}
    
    def _extract_service_details(self, service_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract chi tiết từ service data"""
        try:
            spec = service_data.get('spec', {})
            status = service_data.get('status', {})
            metadata = service_data.get('metadata', {})
            
            ports = spec.get('ports', [])
            port_info = []
            
            for port in ports:
                port_info.append({
                    "port": port.get('port', 0),
                    "targetPort": port.get('targetPort', 0),
                    "protocol": port.get('protocol', 'TCP'),
                    "name": port.get('name', '')
                })
            
            return {
                "type": spec.get('type', 'ClusterIP'),
                "clusterIP": spec.get('clusterIP', ''),
                "ports": port_info,
                "selector": spec.get('selector', {}),
                "creationTimestamp": metadata.get('creationTimestamp', ''),
                "uid": metadata.get('uid', '')
            }
            
        except Exception as e:
            logger.error(f"Error extracting service details: {e}")
            return {}
    
    async def enhance_application_data(self, app_name: str, namespace: str) -> Dict[str, Any]:
        """Bổ sung dữ liệu chi tiết cho application"""
        try:
            logger.info(f"Enhancing data for {app_name} in namespace {namespace}")
            
            # Lấy deployment details
            deployment_details = await self.get_deployment_details(namespace, app_name)
            
            # Lấy service details
            service_details = await self.get_service_details(namespace, f"{app_name}-service")
            
            # Tạo enhanced data
            enhanced_data = {
                "podConfig": {
                    "replicas": deployment_details.get('replicas', 0),
                    "readyReplicas": deployment_details.get('readyReplicas', 0),
                    "availableReplicas": deployment_details.get('availableReplicas', 0),
                    "image": deployment_details.get('container', {}).get('image', ''),
                    "resources": deployment_details.get('container', {}).get('resources', {}),
                    "ports": deployment_details.get('container', {}).get('ports', []),
                    "env": deployment_details.get('container', {}).get('env', []),
                    "livenessProbe": deployment_details.get('container', {}).get('livenessProbe', {}),
                    "readinessProbe": deployment_details.get('container', {}).get('readinessProbe', {})
                },
                "serviceConfig": {
                    "type": service_details.get('type', 'ClusterIP'),
                    "clusterIP": service_details.get('clusterIP', ''),
                    "ports": service_details.get('ports', []),
                    "selector": service_details.get('selector', {})
                },
                "id": deployment_details.get('uid', ''),
                "generation": deployment_details.get('generation', 0)
            }
            
            return enhanced_data
            
        except Exception as e:
            logger.error(f"Error enhancing application data for {app_name}: {e}")
            return {}

async def enhance_all_applications():
    """Bổ sung dữ liệu chi tiết cho tất cả applications"""
    logger.info("🔍 Enhancing all applications with detailed K8s data...")
    
    try:
        # Lấy MongoDB client
        mongo_client = await get_mongodb_client()
        
        # Lấy tất cả applications
        all_apps = await mongo_client.get_all_applications()
        logger.info(f"Found {len(all_apps)} applications to enhance")
        
        # Tạo K8s fetcher
        k8s_fetcher = K8sDetailedFetcher()
        await k8s_fetcher.start_session()
        
        enhanced_count = 0
        
        for app in all_apps:
            app_name = app.get('name', '')
            namespace = app.get('namespace', '')
            
            if app_name and namespace:
                logger.info(f"Enhancing {app_name} in {namespace}...")
                
                # Lấy dữ liệu chi tiết
                enhanced_data = await k8s_fetcher.enhance_application_data(app_name, namespace)
                
                if enhanced_data:
                    # Merge với dữ liệu hiện tại
                    app.update(enhanced_data)
                    
                    # Cập nhật vào MongoDB
                    success = await mongo_client.upsert_application(app)
                    if success:
                        enhanced_count += 1
                        logger.info(f"✅ Enhanced {app_name}")
                    else:
                        logger.warning(f"⚠️ Failed to update {app_name}")
                else:
                    logger.warning(f"⚠️ No enhanced data for {app_name}")
        
        await k8s_fetcher.close_session()
        
        logger.info(f"✅ Enhanced {enhanced_count}/{len(all_apps)} applications")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error enhancing applications: {e}")
        return False

async def main():
    """Main function"""
    logger.info("🚀 Enhance Applications with Detailed K8s Data")
    logger.info("=" * 60)
    
    success = await enhance_all_applications()
    
    if success:
        logger.info("\n✅ Applications enhanced successfully!")
        logger.info("📱 Dashboard will now show detailed information")
    else:
        logger.error("❌ Failed to enhance applications!")
    
    logger.info("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
