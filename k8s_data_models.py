"""
K8s và ArgoCD Data Models cho MongoDB
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class K8sResourceType(str, Enum):
    """Kubernetes resource types"""
    POD = "Pod"
    DEPLOYMENT = "Deployment"
    SERVICE = "Service"
    INGRESS = "Ingress"
    PVC = "PersistentVolumeClaim"
    NAMESPACE = "Namespace"
    CONFIGMAP = "ConfigMap"
    SECRET = "Secret"


class ArgoCDAppStatus(str, Enum):
    """ArgoCD Application status"""
    HEALTHY = "Healthy"
    PROGRESSING = "Progressing"
    DEGRADED = "Degraded"
    SUSPENDED = "Suspended"
    UNKNOWN = "Unknown"


class SyncStatus(str, Enum):
    """Sync status"""
    SYNCED = "Synced"
    OUT_OF_SYNC = "OutOfSync"
    UNKNOWN = "Unknown"


class K8sResourceMetadata(BaseModel):
    """Kubernetes resource metadata"""
    name: str
    namespace: str
    uid: str
    resource_version: str
    creation_timestamp: datetime
    labels: Dict[str, str] = {}
    annotations: Dict[str, str] = {}
    owner_references: List[Dict[str, Any]] = []


class K8sPodSpec(BaseModel):
    """Kubernetes Pod specification"""
    containers: List[Dict[str, Any]]
    init_containers: List[Dict[str, Any]] = []
    volumes: List[Dict[str, Any]] = []
    node_selector: Dict[str, str] = {}
    tolerations: List[Dict[str, Any]] = []
    affinity: Dict[str, Any] = {}


class K8sPodStatus(BaseModel):
    """Kubernetes Pod status"""
    phase: str  # Pending, Running, Succeeded, Failed, Unknown
    conditions: List[Dict[str, Any]] = []
    container_statuses: List[Dict[str, Any]] = []
    start_time: Optional[datetime] = None
    pod_ip: Optional[str] = None
    host_ip: Optional[str] = None
    qos_class: Optional[str] = None


class K8sDeploymentSpec(BaseModel):
    """Kubernetes Deployment specification"""
    replicas: int
    selector: Dict[str, Any]
    template: Dict[str, Any]
    strategy: Dict[str, Any] = {}


class K8sDeploymentStatus(BaseModel):
    """Kubernetes Deployment status"""
    observed_generation: int
    replicas: int
    updated_replicas: int
    ready_replicas: int
    available_replicas: int
    unavailable_replicas: int
    conditions: List[Dict[str, Any]] = []


class K8sServiceSpec(BaseModel):
    """Kubernetes Service specification"""
    type: str  # ClusterIP, NodePort, LoadBalancer, ExternalName
    ports: List[Dict[str, Any]]
    selector: Dict[str, str] = {}
    cluster_ip: Optional[str] = None
    external_ips: List[str] = []


class K8sServiceStatus(BaseModel):
    """Kubernetes Service status"""
    load_balancer: Dict[str, Any] = {}


class K8sResourceData(BaseModel):
    """Kubernetes resource data"""
    kind: K8sResourceType
    api_version: str
    metadata: K8sResourceMetadata
    spec: Optional[Dict[str, Any]] = None
    status: Optional[Dict[str, Any]] = None
    events: List[Dict[str, Any]] = []
    last_sync: datetime = Field(default_factory=datetime.now)


class ArgoCDApplicationSpec(BaseModel):
    """ArgoCD Application specification"""
    project: str
    source: Dict[str, Any]
    destination: Dict[str, Any]
    sync_policy: Optional[Dict[str, Any]] = None
    revision_history_limit: int = 3


class ArgoCDApplicationStatus(BaseModel):
    """ArgoCD Application status"""
    health: ArgoCDAppStatus
    sync: SyncStatus
    resources: List[Dict[str, Any]] = []
    conditions: List[Dict[str, Any]] = []
    operation_state: Optional[Dict[str, Any]] = None
    observed_at: datetime = Field(default_factory=datetime.now)


class ArgoCDApplicationData(BaseModel):
    """ArgoCD Application data"""
    name: str
    namespace: str
    uid: str
    spec: ArgoCDApplicationSpec
    status: ArgoCDApplicationStatus
    metadata: Dict[str, Any] = {}
    last_sync: datetime = Field(default_factory=datetime.now)


class K8sNamespaceData(BaseModel):
    """Kubernetes Namespace data"""
    name: str
    uid: str
    status: str  # Active, Terminating
    labels: Dict[str, str] = {}
    annotations: Dict[str, str] = {}
    resource_quota: Optional[Dict[str, Any]] = None
    limit_range: Optional[Dict[str, Any]] = None
    last_sync: datetime = Field(default_factory=datetime.now)


class ServiceHealthData(BaseModel):
    """Service health data"""
    service_name: str
    namespace: str
    overall_status: str  # healthy, unhealthy, unknown
    k8s_status: str  # running, failed, pending, unknown
    argocd_status: str  # healthy, degraded, progressing, suspended, unknown
    last_health_check: datetime = Field(default_factory=datetime.now)
    health_details: Dict[str, Any] = {}


class ResourceMetrics(BaseModel):
    """Resource usage metrics"""
    cpu_usage: Optional[float] = None  # CPU usage in cores
    memory_usage: Optional[int] = None  # Memory usage in bytes
    cpu_request: Optional[float] = None
    memory_request: Optional[int] = None
    cpu_limit: Optional[float] = None
    memory_limit: Optional[int] = None
    pod_count: Optional[int] = None
    last_updated: datetime = Field(default_factory=datetime.now)


class SyncJobStatus(BaseModel):
    """Sync job status"""
    job_id: str
    job_type: str  # full_sync, incremental_sync, webhook_update
    status: str  # running, completed, failed
    started_at: datetime
    completed_at: Optional[datetime] = None
    resources_synced: int = 0
    errors: List[str] = []
    last_error: Optional[str] = None


class K8sClusterInfo(BaseModel):
    """Kubernetes cluster information"""
    cluster_name: str
    server_version: str
    nodes_count: int
    namespaces: List[str] = []
    total_pods: int = 0
    total_services: int = 0
    total_deployments: int = 0
    last_sync: datetime = Field(default_factory=datetime.now)


class ArgoCDInfo(BaseModel):
    """ArgoCD information"""
    version: str
    applications_count: int
    healthy_apps: int = 0
    degraded_apps: int = 0
    out_of_sync_apps: int = 0
    last_sync: datetime = Field(default_factory=datetime.now)


# MongoDB Collection Models
class K8sResourceDocument(BaseModel):
    """MongoDB document for K8s resources"""
    _id: Optional[str] = None
    resource_type: K8sResourceType
    name: str
    namespace: str
    uid: str
    data: K8sResourceData
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    sync_status: str = "synced"  # synced, out_of_sync, error
    last_event_time: Optional[datetime] = None


class ArgoCDApplicationDocument(BaseModel):
    """MongoDB document for ArgoCD applications"""
    _id: Optional[str] = None
    name: str
    namespace: str
    uid: str
    data: ArgoCDApplicationData
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    sync_status: str = "synced"
    last_sync_time: Optional[datetime] = None


class ServiceHealthDocument(BaseModel):
    """MongoDB document for service health"""
    _id: Optional[str] = None
    service_name: str
    namespace: str
    health_data: ServiceHealthData
    metrics: Optional[ResourceMetrics] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class SyncJobDocument(BaseModel):
    """MongoDB document for sync jobs"""
    _id: Optional[str] = None
    job_id: str
    job_type: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    resources_synced: int = 0
    errors: List[str] = []
    last_error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)


class ClusterInfoDocument(BaseModel):
    """MongoDB document for cluster info"""
    _id: Optional[str] = None
    cluster_type: str  # k8s, argocd
    info: Dict[str, Any]
    last_sync: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
