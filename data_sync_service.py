"""
Data Sync Service - Đồng bộ dữ liệu từ K8s/ArgoCD vào MongoDB
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

from k8s_client import K8sClient, ArgoCDClient
from service_discovery import ServiceDiscovery
from k8s_data_models import (
    K8sResourceDocument, ArgoCDApplicationDocument, ServiceHealthDocument,
    SyncJobDocument, ClusterInfoDocument, K8sResourceData, ArgoCDApplicationData,
    ServiceHealthData, ResourceMetrics, SyncJobStatus
)

logger = logging.getLogger(__name__)


class DataSyncService:
    """Service để đồng bộ dữ liệu từ K8s/ArgoCD vào MongoDB"""
    
    def __init__(self, db: AsyncIOMotorClient, k8s_client: K8sClient, argocd_client: ArgoCDClient):
        self.db = db
        self.k8s_client = k8s_client
        self.argocd_client = argocd_client
        
        # MongoDB collections
        self.k8s_resources = db.devportal.k8s_resources
        self.argocd_applications = db.devportal.argocd_applications
        self.service_health = db.devportal.service_health
        self.sync_jobs = db.devportal.sync_jobs
        self.cluster_info = db.devportal.cluster_info
        
        # Service Discovery
        self.service_discovery = ServiceDiscovery(db, k8s_client)
        
        # Sync settings
        self.sync_interval = 300  # 5 minutes
        self.is_running = False
    
    async def start_sync_service(self):
        """Start the sync service"""
        if self.is_running:
            logger.warning("Sync service is already running")
            return
        
        self.is_running = True
        logger.info("🚀 Starting Data Sync Service")
        
        # Initial sync
        await self.full_sync()
        
        # Start periodic sync
        asyncio.create_task(self._periodic_sync())
    
    async def stop_sync_service(self):
        """Stop the sync service"""
        self.is_running = False
        logger.info("🛑 Stopping Data Sync Service")
    
    async def _periodic_sync(self):
        """Periodic sync task"""
        while self.is_running:
            try:
                await asyncio.sleep(self.sync_interval)
                if self.is_running:
                    await self.incremental_sync()
            except Exception as e:
                logger.error(f"Error in periodic sync: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retry
    
    async def full_sync(self):
        """Perform full sync of all data"""
        job_id = f"full_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"🔄 Starting full sync: {job_id}")
        
        # Create sync job
        sync_job = SyncJobDocument(
            job_id=job_id,
            job_type="full_sync",
            status="running",
            started_at=datetime.now()
        )
        await self.sync_jobs.insert_one(sync_job.dict())
        
        try:
            # Sync cluster info
            await self._sync_cluster_info()
            
            # Sync K8s resources
            await self._sync_k8s_resources()
            
            # Discover existing services from K8s
            await self._discover_existing_services()
            
            # Sync ArgoCD applications
            await self._sync_argocd_applications()
            
            # Update service health
            await self._update_service_health()
            
            # Update sync job as completed
            await self.sync_jobs.update_one(
                {"job_id": job_id},
                {
                    "$set": {
                        "status": "completed",
                        "completed_at": datetime.now()
                    }
                }
            )
            
            logger.info(f"✅ Full sync completed: {job_id}")
            
        except Exception as e:
            logger.error(f"❌ Full sync failed: {e}")
            await self.sync_jobs.update_one(
                {"job_id": job_id},
                {
                    "$set": {
                        "status": "failed",
                        "completed_at": datetime.now(),
                        "last_error": str(e)
                    }
                }
            )
    
    async def incremental_sync(self):
        """Perform incremental sync"""
        job_id = f"incremental_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"🔄 Starting incremental sync: {job_id}")
        
        # Create sync job
        sync_job = SyncJobDocument(
            job_id=job_id,
            job_type="incremental_sync",
            status="running",
            started_at=datetime.now()
        )
        await self.sync_jobs.insert_one(sync_job.dict())
        
        try:
            # Sync only changed resources
            await self._sync_k8s_resources_incremental()
            
            # Discover new services from K8s
            await self._discover_existing_services()
            
            await self._sync_argocd_applications_incremental()
            await self._update_service_health()
            
            # Update sync job as completed
            await self.sync_jobs.update_one(
                {"job_id": job_id},
                {
                    "$set": {
                        "status": "completed",
                        "completed_at": datetime.now()
                    }
                }
            )
            
            logger.info(f"✅ Incremental sync completed: {job_id}")
            
        except Exception as e:
            logger.error(f"❌ Incremental sync failed: {e}")
            await self.sync_jobs.update_one(
                {"job_id": job_id},
                {
                    "$set": {
                        "status": "failed",
                        "completed_at": datetime.now(),
                        "last_error": str(e)
                    }
                }
            )
    
    async def _discover_existing_services(self):
        """Discover existing services from K8s and create service metadata"""
        try:
            logger.info("🔍 Discovering existing services from K8s...")
            
            # Discover services
            discovered_services = await self.service_discovery.discover_existing_services()
            
            # Update existing services
            await self.service_discovery.update_existing_services()
            
            logger.info(f"✅ Service discovery completed. Found {len(discovered_services)} new services")
            
        except Exception as e:
            logger.error(f"Error discovering existing services: {e}")
    
    async def _sync_cluster_info(self):
        """Sync cluster information"""
        try:
            # Get K8s cluster info
            k8s_info = await self.k8s_client.get_cluster_info()
            await self.cluster_info.replace_one(
                {"cluster_type": "k8s"},
                {
                    "cluster_type": "k8s",
                    "info": k8s_info.dict(),
                    "last_sync": datetime.now(),
                    "updated_at": datetime.now()
                },
                upsert=True
            )
            
            # Get ArgoCD info
            argocd_info = await self.argocd_client.get_argocd_info()
            await self.cluster_info.replace_one(
                {"cluster_type": "argocd"},
                {
                    "cluster_type": "argocd",
                    "info": argocd_info.dict(),
                    "last_sync": datetime.now(),
                    "updated_at": datetime.now()
                },
                upsert=True
            )
            
        except Exception as e:
            logger.error(f"Error syncing cluster info: {e}")
    
    async def _sync_k8s_resources(self):
        """Sync all K8s resources"""
        try:
            # Get all namespaces first
            namespaces = await self.k8s_client.get_namespaces()
            
            for namespace in namespaces:
                ns_name = namespace.name
                
                # Sync pods
                pods = await self.k8s_client.get_pods(ns_name)
                await self._save_k8s_resources(pods)
                
                # Sync deployments
                deployments = await self.k8s_client.get_deployments(ns_name)
                await self._save_k8s_resources(deployments)
                
                # Sync services
                services = await self.k8s_client.get_services(ns_name)
                await self._save_k8s_resources(services)
                
                # Sync ingresses
                ingresses = await self.k8s_client.get_ingresses(ns_name)
                await self._save_k8s_resources(ingresses)
            
        except Exception as e:
            logger.error(f"Error syncing K8s resources: {e}")
    
    async def _sync_k8s_resources_incremental(self):
        """Sync only changed K8s resources"""
        try:
            # Get last sync time
            last_sync = await self.sync_jobs.find_one(
                {"job_type": "incremental_sync", "status": "completed"},
                sort=[("completed_at", -1)]
            )
            
            if not last_sync:
                # If no previous sync, do full sync
                await self._sync_k8s_resources()
                return
            
            # For now, do full sync (in production, you'd check resource versions)
            await self._sync_k8s_resources()
            
        except Exception as e:
            logger.error(f"Error in incremental K8s sync: {e}")
    
    async def _save_k8s_resources(self, resources: List[K8sResourceData]):
        """Save K8s resources to MongoDB"""
        for resource in resources:
            try:
                doc = K8sResourceDocument(
                    resource_type=resource.kind,
                    name=resource.metadata.name,
                    namespace=resource.metadata.namespace,
                    uid=resource.metadata.uid,
                    data=resource,
                    sync_status="synced",
                    last_event_time=datetime.now()
                )
                
                await self.k8s_resources.replace_one(
                    {"uid": resource.metadata.uid},
                    doc.dict(),
                    upsert=True
                )
                
            except Exception as e:
                logger.error(f"Error saving K8s resource {resource.metadata.name}: {e}")
    
    async def _sync_argocd_applications(self):
        """Sync ArgoCD applications"""
        try:
            applications = await self.argocd_client.get_applications()
            
            for app in applications:
                try:
                    doc = ArgoCDApplicationDocument(
                        name=app.name,
                        namespace=app.namespace,
                        uid=app.uid,
                        data=app,
                        sync_status="synced",
                        last_sync_time=datetime.now()
                    )
                    
                    await self.argocd_applications.replace_one(
                        {"uid": app.uid},
                        doc.dict(),
                        upsert=True
                    )
                    
                except Exception as e:
                    logger.error(f"Error saving ArgoCD app {app.name}: {e}")
                    
        except Exception as e:
            logger.error(f"Error syncing ArgoCD applications: {e}")
    
    async def _sync_argocd_applications_incremental(self):
        """Sync only changed ArgoCD applications"""
        try:
            # For now, do full sync (in production, you'd check last sync times)
            await self._sync_argocd_applications()
            
        except Exception as e:
            logger.error(f"Error in incremental ArgoCD sync: {e}")
    
    async def _update_service_health(self):
        """Update service health data"""
        try:
            # Get all services from our dev portal
            services = await self.db.devportal.services.find().to_list(None)
            
            for service in services:
                service_name = service["service_name"]
                namespace = service["namespace"]
                
                # Get K8s status
                k8s_status = await self._get_k8s_service_status(service_name, namespace)
                
                # Get ArgoCD status
                argocd_status = await self._get_argocd_service_status(service_name)
                
                # Determine overall health
                overall_status = self._determine_overall_health(k8s_status, argocd_status)
                
                # Get resource metrics
                metrics = await self._get_service_metrics(service_name, namespace)
                
                # Create health data
                health_data = ServiceHealthData(
                    service_name=service_name,
                    namespace=namespace,
                    overall_status=overall_status,
                    k8s_status=k8s_status,
                    argocd_status=argocd_status,
                    last_health_check=datetime.now(),
                    health_details={
                        "k8s_details": await self._get_k8s_service_details(service_name, namespace),
                        "argocd_details": await self._get_argocd_service_details(service_name)
                    }
                )
                
                # Save to MongoDB
                doc = ServiceHealthDocument(
                    service_name=service_name,
                    namespace=namespace,
                    health_data=health_data,
                    metrics=metrics
                )
                
                await self.service_health.replace_one(
                    {"service_name": service_name, "namespace": namespace},
                    doc.dict(),
                    upsert=True
                )
                
        except Exception as e:
            logger.error(f"Error updating service health: {e}")
    
    async def _get_k8s_service_status(self, service_name: str, namespace: str) -> str:
        """Get K8s service status"""
        try:
            # Check if deployment exists and is healthy
            deployment = await self.k8s_resources.find_one({
                "name": service_name,
                "namespace": namespace,
                "resource_type": "Deployment"
            })
            
            if not deployment:
                return "unknown"
            
            status = deployment["data"]["status"]
            ready_replicas = status.get("readyReplicas", 0)
            replicas = status.get("replicas", 0)
            
            if ready_replicas == replicas and replicas > 0:
                return "running"
            elif ready_replicas > 0:
                return "deploying"
            else:
                return "failed"
                
        except Exception as e:
            logger.error(f"Error getting K8s status for {service_name}: {e}")
            return "unknown"
    
    async def _get_argocd_service_status(self, service_name: str) -> str:
        """Get ArgoCD service status"""
        try:
            app = await self.argocd_applications.find_one({
                "name": {"$regex": f".*{service_name}.*", "$options": "i"}
            })
            
            if not app:
                return "unknown"
            
            return app["data"]["status"]["health"]
            
        except Exception as e:
            logger.error(f"Error getting ArgoCD status for {service_name}: {e}")
            return "unknown"
    
    def _determine_overall_health(self, k8s_status: str, argocd_status: str) -> str:
        """Determine overall service health"""
        if k8s_status == "running" and argocd_status == "Healthy":
            return "healthy"
        elif k8s_status in ["deploying", "unknown"] or argocd_status in ["Progressing", "Unknown"]:
            return "unknown"
        else:
            return "unhealthy"
    
    async def _get_service_metrics(self, service_name: str, namespace: str) -> Optional[ResourceMetrics]:
        """Get service resource metrics"""
        try:
            # This would integrate with metrics server
            # For now, return None
            return None
        except Exception as e:
            logger.error(f"Error getting metrics for {service_name}: {e}")
            return None
    
    async def _get_k8s_service_details(self, service_name: str, namespace: str) -> Dict[str, Any]:
        """Get detailed K8s service information"""
        try:
            details = {}
            
            # Get deployment details
            deployment = await self.k8s_resources.find_one({
                "name": service_name,
                "namespace": namespace,
                "resource_type": "Deployment"
            })
            if deployment:
                details["deployment"] = deployment["data"]
            
            # Get service details
            service = await self.k8s_resources.find_one({
                "name": f"{service_name}-service",
                "namespace": namespace,
                "resource_type": "Service"
            })
            if service:
                details["service"] = service["data"]
            
            # Get ingress details
            ingress = await self.k8s_resources.find_one({
                "name": f"{service_name}-ingress",
                "namespace": namespace,
                "resource_type": "Ingress"
            })
            if ingress:
                details["ingress"] = ingress["data"]
            
            return details
            
        except Exception as e:
            logger.error(f"Error getting K8s details for {service_name}: {e}")
            return {}
    
    async def _get_argocd_service_details(self, service_name: str) -> Dict[str, Any]:
        """Get detailed ArgoCD service information"""
        try:
            app = await self.argocd_applications.find_one({
                "name": {"$regex": f".*{service_name}.*", "$options": "i"}
            })
            
            if app:
                return app["data"]
            return {}
            
        except Exception as e:
            logger.error(f"Error getting ArgoCD details for {service_name}: {e}")
            return {}
    
    async def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status"""
        try:
            # Get latest sync jobs
            latest_full_sync = await self.sync_jobs.find_one(
                {"job_type": "full_sync"},
                sort=[("started_at", -1)]
            )
            
            latest_incremental_sync = await self.sync_jobs.find_one(
                {"job_type": "incremental_sync"},
                sort=[("started_at", -1)]
            )
            
            # Get resource counts
            k8s_count = await self.k8s_resources.count_documents({})
            argocd_count = await self.argocd_applications.count_documents({})
            health_count = await self.service_health.count_documents({})
            
            return {
                "is_running": self.is_running,
                "sync_interval": self.sync_interval,
                "latest_full_sync": latest_full_sync,
                "latest_incremental_sync": latest_incremental_sync,
                "resource_counts": {
                    "k8s_resources": k8s_count,
                    "argocd_applications": argocd_count,
                    "service_health": health_count
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting sync status: {e}")
            return {"error": str(e)}
