"""
K8s và ArgoCD API Endpoints
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

from k8s_data_models import (
    K8sResourceDocument, ArgoCDApplicationDocument, ServiceHealthDocument,
    SyncJobDocument, ClusterInfoDocument
)

router = APIRouter(prefix="/api/k8s", tags=["Kubernetes & ArgoCD"])


# Dependency để get database
async def get_database() -> AsyncIOMotorClient:
    from main import client
    return client


# =============================================================================
# K8s Resources API
# =============================================================================

@router.get("/resources")
async def get_k8s_resources(
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    namespace: Optional[str] = Query(None, description="Filter by namespace"),
    limit: int = Query(100, description="Limit number of results"),
    skip: int = Query(0, description="Skip number of results"),
    db: AsyncIOMotorClient = Depends(get_database)
):
    """Get Kubernetes resources"""
    try:
        collection = db.devportal.k8s_resources
        
        # Build filter
        filter_dict = {}
        if resource_type:
            filter_dict["resource_type"] = resource_type
        if namespace:
            filter_dict["namespace"] = namespace
        
        # Get resources
        cursor = collection.find(filter_dict).skip(skip).limit(limit)
        resources = await cursor.to_list(length=limit)
        
        # Convert to response format
        result = []
        for resource in resources:
            result.append({
                "id": str(resource["_id"]),
                "resource_type": resource["resource_type"],
                "name": resource["name"],
                "namespace": resource["namespace"],
                "uid": resource["uid"],
                "created_at": resource["created_at"],
                "updated_at": resource["updated_at"],
                "sync_status": resource["sync_status"],
                "data": resource["data"]
            })
        
        # Get total count
        total_count = await collection.count_documents(filter_dict)
        
        return {
            "status": "success",
            "total": total_count,
            "limit": limit,
            "skip": skip,
            "resources": result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting K8s resources: {str(e)}")


@router.get("/resources/{resource_id}")
async def get_k8s_resource(
    resource_id: str,
    db: AsyncIOMotorClient = Depends(get_database)
):
    """Get specific Kubernetes resource"""
    try:
        collection = db.devportal.k8s_resources
        resource = await collection.find_one({"_id": ObjectId(resource_id)})
        
        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        return {
            "status": "success",
            "resource": {
                "id": str(resource["_id"]),
                "resource_type": resource["resource_type"],
                "name": resource["name"],
                "namespace": resource["namespace"],
                "uid": resource["uid"],
                "created_at": resource["created_at"],
                "updated_at": resource["updated_at"],
                "sync_status": resource["sync_status"],
                "data": resource["data"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting K8s resource: {str(e)}")


@router.get("/resources/namespace/{namespace}")
async def get_namespace_resources(
    namespace: str,
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    db: AsyncIOMotorClient = Depends(get_database)
):
    """Get all resources in a specific namespace"""
    try:
        collection = db.devportal.k8s_resources
        
        filter_dict = {"namespace": namespace}
        if resource_type:
            filter_dict["resource_type"] = resource_type
        
        cursor = collection.find(filter_dict)
        resources = await cursor.to_list(length=None)
        
        result = []
        for resource in resources:
            result.append({
                "id": str(resource["_id"]),
                "resource_type": resource["resource_type"],
                "name": resource["name"],
                "namespace": resource["namespace"],
                "uid": resource["uid"],
                "sync_status": resource["sync_status"],
                "data": resource["data"]
            })
        
        return {
            "status": "success",
            "namespace": namespace,
            "total": len(result),
            "resources": result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting namespace resources: {str(e)}")


# =============================================================================
# ArgoCD Applications API
# =============================================================================

@router.get("/applications")
async def get_argocd_applications(
    status: Optional[str] = Query(None, description="Filter by health status"),
    sync_status: Optional[str] = Query(None, description="Filter by sync status"),
    limit: int = Query(100, description="Limit number of results"),
    skip: int = Query(0, description="Skip number of results"),
    db: AsyncIOMotorClient = Depends(get_database)
):
    """Get ArgoCD applications"""
    try:
        collection = db.devportal.argocd_applications
        
        # Build filter
        filter_dict = {}
        if status:
            filter_dict["data.status.health"] = status
        if sync_status:
            filter_dict["data.status.sync"] = sync_status
        
        # Get applications
        cursor = collection.find(filter_dict).skip(skip).limit(limit)
        applications = await cursor.to_list(length=limit)
        
        # Convert to response format
        result = []
        for app in applications:
            result.append({
                "id": str(app["_id"]),
                "name": app["name"],
                "namespace": app["namespace"],
                "uid": app["uid"],
                "created_at": app["created_at"],
                "updated_at": app["updated_at"],
                "sync_status": app["sync_status"],
                "data": app["data"]
            })
        
        # Get total count
        total_count = await collection.count_documents(filter_dict)
        
        return {
            "status": "success",
            "total": total_count,
            "limit": limit,
            "skip": skip,
            "applications": result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting ArgoCD applications: {str(e)}")


@router.get("/applications/{app_name}")
async def get_argocd_application(
    app_name: str,
    db: AsyncIOMotorClient = Depends(get_database)
):
    """Get specific ArgoCD application"""
    try:
        collection = db.devportal.argocd_applications
        app = await collection.find_one({"name": app_name})
        
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        
        return {
            "status": "success",
            "application": {
                "id": str(app["_id"]),
                "name": app["name"],
                "namespace": app["namespace"],
                "uid": app["uid"],
                "created_at": app["created_at"],
                "updated_at": app["updated_at"],
                "sync_status": app["sync_status"],
                "data": app["data"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting ArgoCD application: {str(e)}")


# =============================================================================
# Service Health API
# =============================================================================

@router.get("/health")
async def get_service_health(
    service_name: Optional[str] = Query(None, description="Filter by service name"),
    namespace: Optional[str] = Query(None, description="Filter by namespace"),
    health_status: Optional[str] = Query(None, description="Filter by health status"),
    limit: int = Query(100, description="Limit number of results"),
    skip: int = Query(0, description="Skip number of results"),
    db: AsyncIOMotorClient = Depends(get_database)
):
    """Get service health data"""
    try:
        collection = db.devportal.service_health
        
        # Build filter
        filter_dict = {}
        if service_name:
            filter_dict["service_name"] = service_name
        if namespace:
            filter_dict["namespace"] = namespace
        if health_status:
            filter_dict["health_data.overall_status"] = health_status
        
        # Get health data
        cursor = collection.find(filter_dict).skip(skip).limit(limit)
        health_data = await cursor.to_list(length=limit)
        
        # Convert to response format
        result = []
        for health in health_data:
            result.append({
                "id": str(health["_id"]),
                "service_name": health["service_name"],
                "namespace": health["namespace"],
                "created_at": health["created_at"],
                "updated_at": health["updated_at"],
                "health_data": health["health_data"],
                "metrics": health.get("metrics")
            })
        
        # Get total count
        total_count = await collection.count_documents(filter_dict)
        
        return {
            "status": "success",
            "total": total_count,
            "limit": limit,
            "skip": skip,
            "health_data": result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting service health: {str(e)}")


@router.get("/health/{service_name}")
async def get_service_health_detail(
    service_name: str,
    db: AsyncIOMotorClient = Depends(get_database)
):
    """Get detailed health data for a specific service"""
    try:
        collection = db.devportal.service_health
        health = await collection.find_one({"service_name": service_name})
        
        if not health:
            raise HTTPException(status_code=404, detail="Service health data not found")
        
        return {
            "status": "success",
            "health": {
                "id": str(health["_id"]),
                "service_name": health["service_name"],
                "namespace": health["namespace"],
                "created_at": health["created_at"],
                "updated_at": health["updated_at"],
                "health_data": health["health_data"],
                "metrics": health.get("metrics")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting service health detail: {str(e)}")


@router.get("/health/summary")
async def get_health_summary(db: AsyncIOMotorClient = Depends(get_database)):
    """Get health summary for all services"""
    try:
        collection = db.devportal.service_health
        
        # Get all health data
        cursor = collection.find({})
        all_health = await cursor.to_list(length=None)
        
        # Calculate summary
        total_services = len(all_health)
        healthy_services = len([h for h in all_health if h["health_data"]["overall_status"] == "healthy"])
        unhealthy_services = len([h for h in all_health if h["health_data"]["overall_status"] == "unhealthy"])
        unknown_services = len([h for h in all_health if h["health_data"]["overall_status"] == "unknown"])
        
        # Group by namespace
        namespace_summary = {}
        for health in all_health:
            namespace = health["namespace"]
            if namespace not in namespace_summary:
                namespace_summary[namespace] = {
                    "total": 0,
                    "healthy": 0,
                    "unhealthy": 0,
                    "unknown": 0
                }
            
            namespace_summary[namespace]["total"] += 1
            status = health["health_data"]["overall_status"]
            if status == "healthy":
                namespace_summary[namespace]["healthy"] += 1
            elif status == "unhealthy":
                namespace_summary[namespace]["unhealthy"] += 1
            else:
                namespace_summary[namespace]["unknown"] += 1
        
        return {
            "status": "success",
            "summary": {
                "total_services": total_services,
                "healthy_services": healthy_services,
                "unhealthy_services": unhealthy_services,
                "unknown_services": unknown_services,
                "health_percentage": round((healthy_services / total_services * 100) if total_services > 0 else 0, 2)
            },
            "by_namespace": namespace_summary
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting health summary: {str(e)}")


# =============================================================================
# Cluster Info API
# =============================================================================

@router.get("/cluster/info")
async def get_cluster_info(db: AsyncIOMotorClient = Depends(get_database)):
    """Get cluster information"""
    try:
        collection = db.devportal.cluster_info
        
        # Get K8s cluster info
        k8s_info = await collection.find_one({"cluster_type": "k8s"})
        
        # Get ArgoCD info
        argocd_info = await collection.find_one({"cluster_type": "argocd"})
        
        return {
            "status": "success",
            "k8s_cluster": k8s_info["info"] if k8s_info else None,
            "argocd": argocd_info["info"] if argocd_info else None,
            "last_sync": {
                "k8s": k8s_info["last_sync"] if k8s_info else None,
                "argocd": argocd_info["last_sync"] if argocd_info else None
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting cluster info: {str(e)}")


# =============================================================================
# Sync Jobs API
# =============================================================================

@router.get("/sync/jobs")
async def get_sync_jobs(
    job_type: Optional[str] = Query(None, description="Filter by job type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, description="Limit number of results"),
    skip: int = Query(0, description="Skip number of results"),
    db: AsyncIOMotorClient = Depends(get_database)
):
    """Get sync jobs"""
    try:
        collection = db.devportal.sync_jobs
        
        # Build filter
        filter_dict = {}
        if job_type:
            filter_dict["job_type"] = job_type
        if status:
            filter_dict["status"] = status
        
        # Get jobs
        cursor = collection.find(filter_dict).sort("started_at", -1).skip(skip).limit(limit)
        jobs = await cursor.to_list(length=limit)
        
        # Convert to response format
        result = []
        for job in jobs:
            result.append({
                "id": str(job["_id"]),
                "job_id": job["job_id"],
                "job_type": job["job_type"],
                "status": job["status"],
                "started_at": job["started_at"],
                "completed_at": job.get("completed_at"),
                "resources_synced": job.get("resources_synced", 0),
                "errors": job.get("errors", []),
                "last_error": job.get("last_error")
            })
        
        # Get total count
        total_count = await collection.count_documents(filter_dict)
        
        return {
            "status": "success",
            "total": total_count,
            "limit": limit,
            "skip": skip,
            "jobs": result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting sync jobs: {str(e)}")


@router.get("/sync/status")
async def get_sync_status(db: AsyncIOMotorClient = Depends(get_database)):
    """Get current sync status"""
    try:
        # Get latest sync jobs
        collection = db.devportal.sync_jobs
        
        latest_full_sync = await collection.find_one(
            {"job_type": "full_sync"},
            sort=[("started_at", -1)]
        )
        
        latest_incremental_sync = await collection.find_one(
            {"job_type": "incremental_sync"},
            sort=[("started_at", -1)]
        )
        
        # Get resource counts
        k8s_count = await db.devportal.k8s_resources.count_documents({})
        argocd_count = await db.devportal.argocd_applications.count_documents({})
        health_count = await db.devportal.service_health.count_documents({})
        
        return {
            "status": "success",
            "latest_full_sync": latest_full_sync,
            "latest_incremental_sync": latest_incremental_sync,
            "resource_counts": {
                "k8s_resources": k8s_count,
                "argocd_applications": argocd_count,
                "service_health": health_count
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting sync status: {str(e)}")


# =============================================================================
# Statistics API
# =============================================================================

@router.get("/stats/overview")
async def get_overview_stats(db: AsyncIOMotorClient = Depends(get_database)):
    """Get overview statistics"""
    try:
        # Get resource counts by type
        k8s_collection = db.devportal.k8s_resources
        argocd_collection = db.devportal.argocd_applications
        health_collection = db.devportal.service_health
        
        # K8s resources by type
        k8s_pipeline = [
            {"$group": {"_id": "$resource_type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        k8s_by_type = await k8s_collection.aggregate(k8s_pipeline).to_list(None)
        
        # ArgoCD apps by status
        argocd_pipeline = [
            {"$group": {"_id": "$data.status.health", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        argocd_by_status = await argocd_collection.aggregate(argocd_pipeline).to_list(None)
        
        # Health by status
        health_pipeline = [
            {"$group": {"_id": "$health_data.overall_status", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        health_by_status = await health_collection.aggregate(health_pipeline).to_list(None)
        
        # Namespace distribution
        namespace_pipeline = [
            {"$group": {"_id": "$namespace", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        namespace_dist = await k8s_collection.aggregate(namespace_pipeline).to_list(None)
        
        return {
            "status": "success",
            "overview": {
                "k8s_resources_by_type": k8s_by_type,
                "argocd_apps_by_status": argocd_by_status,
                "health_by_status": health_by_status,
                "namespace_distribution": namespace_dist
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting overview stats: {str(e)}")


@router.get("/stats/namespaces")
async def get_namespace_stats(db: AsyncIOMotorClient = Depends(get_database)):
    """Get namespace statistics"""
    try:
        k8s_collection = db.devportal.k8s_resources
        
        # Get resources per namespace
        pipeline = [
            {
                "$group": {
                    "_id": "$namespace",
                    "total_resources": {"$sum": 1},
                    "resource_types": {"$addToSet": "$resource_type"},
                    "pods": {"$sum": {"$cond": [{"$eq": ["$resource_type", "Pod"]}, 1, 0]}},
                    "deployments": {"$sum": {"$cond": [{"$eq": ["$resource_type", "Deployment"]}, 1, 0]}},
                    "services": {"$sum": {"$cond": [{"$eq": ["$resource_type", "Service"]}, 1, 0]}},
                    "ingresses": {"$sum": {"$cond": [{"$eq": ["$resource_type", "Ingress"]}, 1, 0]}}
                }
            },
            {"$sort": {"total_resources": -1}}
        ]
        
        namespace_stats = await k8s_collection.aggregate(pipeline).to_list(None)
        
        return {
            "status": "success",
            "namespace_stats": namespace_stats
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting namespace stats: {str(e)}")
