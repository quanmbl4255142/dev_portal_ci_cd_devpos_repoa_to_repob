"""
Service Discovery - Tự động phát hiện và tạo service metadata cho các service có sẵn trong K8s
"""
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorClient

from k8s_client import K8sClient
from k8s_data_models import K8sResourceData, K8sResourceType

logger = logging.getLogger(__name__)


class ServiceDiscovery:
    """Service để phát hiện và tạo service metadata cho các service có sẵn trong K8s"""
    
    def __init__(self, db: AsyncIOMotorClient, k8s_client: K8sClient):
        self.db = db
        self.k8s_client = k8s_client
        self.services_collection = db.devportal.services
        self.k8s_resources_collection = db.devportal.k8s_resources
    
    async def discover_existing_services(self):
        """Phát hiện và tạo service metadata cho các service có sẵn trong K8s"""
        try:
            logger.info("🔍 Starting service discovery...")
            
            # Lấy tất cả deployments từ K8s
            deployments = await self.k8s_client.get_deployments()
            
            discovered_services = []
            
            for deployment in deployments:
                try:
                    # Kiểm tra xem service đã tồn tại trong MongoDB chưa
                    service_name = deployment.metadata.name
                    namespace = deployment.metadata.namespace
                    
                    existing_service = await self.services_collection.find_one({
                        "service_name": service_name,
                        "namespace": namespace
                    })
                    
                    if existing_service:
                        logger.debug(f"⏭️  Service {service_name} already exists in MongoDB")
                        continue
                    
                    # Tạo service metadata mới
                    service_metadata = await self._create_service_metadata(deployment)
                    
                    if service_metadata:
                        # Lưu vào MongoDB
                        await self.services_collection.insert_one(service_metadata)
                        discovered_services.append(service_metadata)
                        logger.info(f"✅ Discovered and created service: {service_name}")
                    
                except Exception as e:
                    logger.error(f"❌ Error processing deployment {deployment.metadata.name}: {e}")
                    continue
            
            logger.info(f"🎉 Service discovery completed. Found {len(discovered_services)} new services")
            return discovered_services
            
        except Exception as e:
            logger.error(f"❌ Error in service discovery: {e}")
            return []
    
    async def _create_service_metadata(self, deployment: K8sResourceData) -> Optional[Dict[str, Any]]:
        """Tạo service metadata từ deployment data"""
        try:
            service_name = deployment.metadata.name
            namespace = deployment.metadata.namespace
            
            # Lấy thông tin từ deployment spec
            spec = deployment.spec or {}
            template = spec.get("template", {})
            containers = template.get("spec", {}).get("containers", [])
            
            if not containers:
                logger.warning(f"No containers found in deployment {service_name}")
                return None
            
            # Lấy container đầu tiên (thường là main container)
            main_container = containers[0]
            docker_image = main_container.get("image", "unknown")
            
            # Lấy resource requirements
            resources = main_container.get("resources", {})
            requests = resources.get("requests", {})
            limits = resources.get("limits", {})
            
            # Lấy replicas
            replicas = spec.get("replicas", 1)
            
            # Lấy labels và annotations
            labels = deployment.metadata.labels or {}
            annotations = deployment.metadata.annotations or {}
            
            # Tạo k8s_config
            k8s_config = {
                "memory_request": requests.get("memory", "256Mi"),
                "memory_limit": limits.get("memory", "512Mi"),
                "cpu_request": requests.get("cpu", "250m"),
                "cpu_limit": limits.get("cpu", "500m"),
                "replicas": replicas,
                "port": 8000,  # Default port
                "pvc_size": "1Gi",
                "storage_class": "standard",
                "domain": f"{service_name}.yourdomain.com",
                "enable_tls": True,
                "liveness_initial_delay": 30,
                "readiness_initial_delay": 5
            }
            
            # Tạo service metadata
            service_metadata = {
                "service_name": service_name,
                "project_name": service_name.replace("-", "_"),
                "app_name": "api",  # Default app name
                "namespace": namespace,
                "docker_image": docker_image,
                "repository_a_url": None,  # Unknown for existing services
                "repository_b_url": None,  # Unknown for existing services
                "k8s_config": k8s_config,
                "models": [],  # Unknown for existing services
                "status": "running",  # Assume running
                "health_status": "unknown",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "last_deployed": None,
                "argocd_app_name": f"{service_name}-app",
                "ingress_url": f"https://{service_name}.yourdomain.com",
                "github_workflow_url": None,
                "error_message": None,
                "discovered_from_k8s": True,  # Flag để biết service được discover từ K8s
                "k8s_labels": labels,
                "k8s_annotations": annotations,
                "creation_timestamp": deployment.metadata.creation_timestamp
            }
            
            return service_metadata
            
        except Exception as e:
            logger.error(f"Error creating service metadata for {deployment.metadata.name}: {e}")
            return None
    
    async def update_existing_services(self):
        """Cập nhật thông tin cho các service đã tồn tại"""
        try:
            logger.info("🔄 Updating existing services...")
            
            # Lấy tất cả services từ MongoDB
            services = await self.services_collection.find({}).to_list(None)
            
            updated_count = 0
            
            for service in services:
                try:
                    service_name = service["service_name"]
                    namespace = service["namespace"]
                    
                    # Lấy deployment từ K8s
                    deployments = await self.k8s_client.get_deployments(namespace)
                    deployment = next(
                        (d for d in deployments if d.metadata.name == service_name), 
                        None
                    )
                    
                    if not deployment:
                        logger.warning(f"Deployment {service_name} not found in K8s")
                        continue
                    
                    # Cập nhật thông tin từ K8s
                    await self._update_service_from_k8s(service, deployment)
                    updated_count += 1
                    
                except Exception as e:
                    logger.error(f"Error updating service {service['service_name']}: {e}")
                    continue
            
            logger.info(f"✅ Updated {updated_count} existing services")
            
        except Exception as e:
            logger.error(f"❌ Error updating existing services: {e}")
    
    async def _update_service_from_k8s(self, service: Dict[str, Any], deployment: K8sResourceData):
        """Cập nhật service từ K8s deployment data"""
        try:
            service_name = service["service_name"]
            namespace = service["namespace"]
            
            # Lấy thông tin mới từ deployment
            spec = deployment.spec or {}
            template = spec.get("template", {})
            containers = template.get("spec", {}).get("containers", [])
            
            if not containers:
                return
            
            main_container = containers[0]
            docker_image = main_container.get("image", service.get("docker_image", "unknown"))
            
            # Lấy resource requirements
            resources = main_container.get("resources", {})
            requests = resources.get("requests", {})
            limits = resources.get("limits", {})
            
            # Lấy replicas
            replicas = spec.get("replicas", 1)
            
            # Lấy labels và annotations
            labels = deployment.metadata.labels or {}
            annotations = deployment.metadata.annotations or {}
            
            # Cập nhật k8s_config
            k8s_config = service.get("k8s_config", {})
            k8s_config.update({
                "memory_request": requests.get("memory", k8s_config.get("memory_request", "256Mi")),
                "memory_limit": limits.get("memory", k8s_config.get("memory_limit", "512Mi")),
                "cpu_request": requests.get("cpu", k8s_config.get("cpu_request", "250m")),
                "cpu_limit": limits.get("cpu", k8s_config.get("cpu_limit", "500m")),
                "replicas": replicas
            })
            
            # Cập nhật service
            await self.services_collection.update_one(
                {"_id": service["_id"]},
                {
                    "$set": {
                        "docker_image": docker_image,
                        "k8s_config": k8s_config,
                        "k8s_labels": labels,
                        "k8s_annotations": annotations,
                        "updated_at": datetime.now(),
                        "last_k8s_sync": datetime.now()
                    }
                }
            )
            
            logger.debug(f"Updated service {service_name} from K8s")
            
        except Exception as e:
            logger.error(f"Error updating service {service['service_name']} from K8s: {e}")
    
    async def discover_services_by_namespace(self, namespace: str):
        """Phát hiện services trong namespace cụ thể"""
        try:
            logger.info(f"🔍 Discovering services in namespace: {namespace}")
            
            # Lấy deployments trong namespace
            deployments = await self.k8s_client.get_deployments(namespace)
            
            discovered_services = []
            
            for deployment in deployments:
                try:
                    service_name = deployment.metadata.name
                    
                    # Kiểm tra xem service đã tồn tại chưa
                    existing_service = await self.services_collection.find_one({
                        "service_name": service_name,
                        "namespace": namespace
                    })
                    
                    if existing_service:
                        continue
                    
                    # Tạo service metadata
                    service_metadata = await self._create_service_metadata(deployment)
                    
                    if service_metadata:
                        await self.services_collection.insert_one(service_metadata)
                        discovered_services.append(service_metadata)
                        logger.info(f"✅ Discovered service in {namespace}: {service_name}")
                    
                except Exception as e:
                    logger.error(f"Error processing deployment {deployment.metadata.name}: {e}")
                    continue
            
            logger.info(f"🎉 Discovered {len(discovered_services)} services in namespace {namespace}")
            return discovered_services
            
        except Exception as e:
            logger.error(f"❌ Error discovering services in namespace {namespace}: {e}")
            return []
    
    async def get_discovery_summary(self) -> Dict[str, Any]:
        """Lấy tóm tắt về service discovery"""
        try:
            # Đếm services được discover từ K8s
            discovered_services = await self.services_collection.count_documents({
                "discovered_from_k8s": True
            })
            
            # Đếm tổng số services
            total_services = await self.services_collection.count_documents({})
            
            # Đếm services theo namespace
            namespace_stats = await self.services_collection.aggregate([
                {"$group": {
                    "_id": "$namespace",
                    "count": {"$sum": 1},
                    "discovered_count": {
                        "$sum": {"$cond": [{"$eq": ["$discovered_from_k8s", True]}, 1, 0]}
                    }
                }},
                {"$sort": {"count": -1}}
            ]).to_list(None)
            
            return {
                "total_services": total_services,
                "discovered_services": discovered_services,
                "manual_services": total_services - discovered_services,
                "namespace_stats": namespace_stats
            }
            
        except Exception as e:
            logger.error(f"Error getting discovery summary: {e}")
            return {}
