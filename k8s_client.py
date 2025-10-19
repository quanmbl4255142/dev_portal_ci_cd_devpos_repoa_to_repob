"""
Kubernetes và ArgoCD Client Service
"""
import asyncio
import json
import subprocess
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from k8s_data_models import (
    K8sResourceData, K8sResourceType, K8sResourceMetadata,
    ArgoCDApplicationData, ArgoCDApplicationSpec, ArgoCDApplicationStatus,
    K8sNamespaceData, K8sClusterInfo, ArgoCDInfo
)

logger = logging.getLogger(__name__)


class K8sClient:
    """Kubernetes client for fetching cluster data"""
    
    def __init__(self, kubeconfig_path: Optional[str] = None):
        self.kubeconfig_path = kubeconfig_path
        self.kubectl_cmd = ["kubectl"]
        if kubeconfig_path:
            self.kubectl_cmd.extend(["--kubeconfig", kubeconfig_path])
    
    async def _run_kubectl(self, args: List[str]) -> Dict[str, Any]:
        """Run kubectl command and return JSON output"""
        try:
            cmd = self.kubectl_cmd + args + ["-o", "json"]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"kubectl command failed: {stderr.decode()}")
                return {}
            
            return json.loads(stdout.decode())
        except Exception as e:
            logger.error(f"Error running kubectl: {e}")
            return {}
    
    async def get_cluster_info(self) -> K8sClusterInfo:
        """Get Kubernetes cluster information"""
        try:
            # Get cluster version
            version_info = await self._run_kubectl(["version", "--client", "--output=json"])
            server_version = version_info.get("serverVersion", {}).get("gitVersion", "unknown")
            
            # Get nodes
            nodes = await self._run_kubectl(["get", "nodes"])
            nodes_count = len(nodes.get("items", []))
            
            # Get namespaces
            namespaces = await self._run_kubectl(["get", "namespaces"])
            namespace_names = [ns["metadata"]["name"] for ns in namespaces.get("items", [])]
            
            # Get resource counts
            pods = await self._run_kubectl(["get", "pods", "--all-namespaces"])
            services = await self._run_kubectl(["get", "services", "--all-namespaces"])
            deployments = await self._run_kubectl(["get", "deployments", "--all-namespaces"])
            
            return K8sClusterInfo(
                cluster_name="dev-cluster",  # Could be fetched from context
                server_version=server_version,
                nodes_count=nodes_count,
                namespaces=namespace_names,
                total_pods=len(pods.get("items", [])),
                total_services=len(services.get("items", [])),
                total_deployments=len(deployments.get("items", [])),
                last_sync=datetime.now()
            )
        except Exception as e:
            logger.error(f"Error getting cluster info: {e}")
            return K8sClusterInfo(
                cluster_name="unknown",
                server_version="unknown",
                nodes_count=0,
                last_sync=datetime.now()
            )
    
    async def get_namespaces(self) -> List[K8sNamespaceData]:
        """Get all namespaces"""
        try:
            namespaces = await self._run_kubectl(["get", "namespaces"])
            result = []
            
            for ns in namespaces.get("items", []):
                metadata = ns["metadata"]
                status = ns["status"]["phase"]
                
                result.append(K8sNamespaceData(
                    name=metadata["name"],
                    uid=metadata["uid"],
                    status=status,
                    labels=metadata.get("labels", {}),
                    annotations=metadata.get("annotations", {}),
                    last_sync=datetime.now()
                ))
            
            return result
        except Exception as e:
            logger.error(f"Error getting namespaces: {e}")
            return []
    
    async def get_pods(self, namespace: Optional[str] = None) -> List[K8sResourceData]:
        """Get pods from namespace or all namespaces"""
        try:
            args = ["get", "pods"]
            if namespace:
                args.extend(["-n", namespace])
            else:
                args.append("--all-namespaces")
            
            pods = await self._run_kubectl(args)
            result = []
            
            for pod in pods.get("items", []):
                metadata = pod["metadata"]
                spec = pod.get("spec", {})
                status = pod.get("status", {})
                
                resource_metadata = K8sResourceMetadata(
                    name=metadata["name"],
                    namespace=metadata["namespace"],
                    uid=metadata["uid"],
                    resource_version=metadata["resourceVersion"],
                    creation_timestamp=datetime.fromisoformat(
                        metadata["creationTimestamp"].replace("Z", "+00:00")
                    ),
                    labels=metadata.get("labels", {}),
                    annotations=metadata.get("annotations", {}),
                    owner_references=metadata.get("ownerReferences", [])
                )
                
                result.append(K8sResourceData(
                    kind=K8sResourceType.POD,
                    api_version=pod["apiVersion"],
                    metadata=resource_metadata,
                    spec=spec,
                    status=status,
                    last_sync=datetime.now()
                ))
            
            return result
        except Exception as e:
            logger.error(f"Error getting pods: {e}")
            return []
    
    async def get_deployments(self, namespace: Optional[str] = None) -> List[K8sResourceData]:
        """Get deployments from namespace or all namespaces"""
        try:
            args = ["get", "deployments"]
            if namespace:
                args.extend(["-n", namespace])
            else:
                args.append("--all-namespaces")
            
            deployments = await self._run_kubectl(args)
            result = []
            
            for deployment in deployments.get("items", []):
                metadata = deployment["metadata"]
                spec = deployment.get("spec", {})
                status = deployment.get("status", {})
                
                resource_metadata = K8sResourceMetadata(
                    name=metadata["name"],
                    namespace=metadata["namespace"],
                    uid=metadata["uid"],
                    resource_version=metadata["resourceVersion"],
                    creation_timestamp=datetime.fromisoformat(
                        metadata["creationTimestamp"].replace("Z", "+00:00")
                    ),
                    labels=metadata.get("labels", {}),
                    annotations=metadata.get("annotations", {}),
                    owner_references=metadata.get("ownerReferences", [])
                )
                
                result.append(K8sResourceData(
                    kind=K8sResourceType.DEPLOYMENT,
                    api_version=deployment["apiVersion"],
                    metadata=resource_metadata,
                    spec=spec,
                    status=status,
                    last_sync=datetime.now()
                ))
            
            return result
        except Exception as e:
            logger.error(f"Error getting deployments: {e}")
            return []
    
    async def get_services(self, namespace: Optional[str] = None) -> List[K8sResourceData]:
        """Get services from namespace or all namespaces"""
        try:
            args = ["get", "services"]
            if namespace:
                args.extend(["-n", namespace])
            else:
                args.append("--all-namespaces")
            
            services = await self._run_kubectl(args)
            result = []
            
            for service in services.get("items", []):
                metadata = service["metadata"]
                spec = service.get("spec", {})
                status = service.get("status", {})
                
                resource_metadata = K8sResourceMetadata(
                    name=metadata["name"],
                    namespace=metadata["namespace"],
                    uid=metadata["uid"],
                    resource_version=metadata["resourceVersion"],
                    creation_timestamp=datetime.fromisoformat(
                        metadata["creationTimestamp"].replace("Z", "+00:00")
                    ),
                    labels=metadata.get("labels", {}),
                    annotations=metadata.get("annotations", {}),
                    owner_references=metadata.get("ownerReferences", [])
                )
                
                result.append(K8sResourceData(
                    kind=K8sResourceType.SERVICE,
                    api_version=service["apiVersion"],
                    metadata=resource_metadata,
                    spec=spec,
                    status=status,
                    last_sync=datetime.now()
                ))
            
            return result
        except Exception as e:
            logger.error(f"Error getting services: {e}")
            return []
    
    async def get_ingresses(self, namespace: Optional[str] = None) -> List[K8sResourceData]:
        """Get ingresses from namespace or all namespaces"""
        try:
            args = ["get", "ingresses"]
            if namespace:
                args.extend(["-n", namespace])
            else:
                args.append("--all-namespaces")
            
            ingresses = await self._run_kubectl(args)
            result = []
            
            for ingress in ingresses.get("items", []):
                metadata = ingress["metadata"]
                spec = ingress.get("spec", {})
                status = ingress.get("status", {})
                
                resource_metadata = K8sResourceMetadata(
                    name=metadata["name"],
                    namespace=metadata["namespace"],
                    uid=metadata["uid"],
                    resource_version=metadata["resourceVersion"],
                    creation_timestamp=datetime.fromisoformat(
                        metadata["creationTimestamp"].replace("Z", "+00:00")
                    ),
                    labels=metadata.get("labels", {}),
                    annotations=metadata.get("annotations", {}),
                    owner_references=metadata.get("ownerReferences", [])
                )
                
                result.append(K8sResourceData(
                    kind=K8sResourceType.INGRESS,
                    api_version=ingress["apiVersion"],
                    metadata=resource_metadata,
                    spec=spec,
                    status=status,
                    last_sync=datetime.now()
                ))
            
            return result
        except Exception as e:
            logger.error(f"Error getting ingresses: {e}")
            return []
    
    async def get_events(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get events from namespace or all namespaces"""
        try:
            args = ["get", "events"]
            if namespace:
                args.extend(["-n", namespace])
            else:
                args.append("--all-namespaces")
            
            events = await self._run_kubectl(args)
            return events.get("items", [])
        except Exception as e:
            logger.error(f"Error getting events: {e}")
            return []
    
    async def get_resource_metrics(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """Get resource usage metrics"""
        try:
            # Get pod metrics
            args = ["top", "pods"]
            if namespace:
                args.extend(["-n", namespace])
            else:
                args.append("--all-namespaces")
            
            pod_metrics = await self._run_kubectl(args)
            
            # Get node metrics
            node_metrics = await self._run_kubectl(["top", "nodes"])
            
            return {
                "pod_metrics": pod_metrics,
                "node_metrics": node_metrics,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return {}


class ArgoCDClient:
    """ArgoCD client for fetching application data"""
    
    def __init__(self, argocd_server: str = "argocd-server.argocd.svc.cluster.local:443"):
        self.argocd_server = argocd_server
        self.argocd_cmd = ["argocd"]
    
    async def _run_argocd(self, args: List[str]) -> Dict[str, Any]:
        """Run argocd command and return JSON output"""
        try:
            cmd = self.argocd_cmd + args + ["--output", "json"]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"argocd command failed: {stderr.decode()}")
                return {}
            
            return json.loads(stdout.decode())
        except Exception as e:
            logger.error(f"Error running argocd: {e}")
            return {}
    
    async def get_applications(self) -> List[ArgoCDApplicationData]:
        """Get all ArgoCD applications"""
        try:
            apps = await self._run_argocd(["app", "list"])
            result = []
            
            for app in apps:
                name = app.get("name", "")
                namespace = app.get("namespace", "argocd")
                
                # Get detailed app info
                app_details = await self._run_argocd(["app", "get", name])
                
                spec = ArgoCDApplicationSpec(
                    project=app_details.get("spec", {}).get("project", "default"),
                    source=app_details.get("spec", {}).get("source", {}),
                    destination=app_details.get("spec", {}).get("destination", {}),
                    sync_policy=app_details.get("spec", {}).get("syncPolicy"),
                    revision_history_limit=app_details.get("spec", {}).get("revisionHistoryLimit", 3)
                )
                
                status = ArgoCDApplicationStatus(
                    health=app_details.get("status", {}).get("health", {}).get("status", "Unknown"),
                    sync=app_details.get("status", {}).get("sync", {}).get("status", "Unknown"),
                    resources=app_details.get("status", {}).get("resources", []),
                    conditions=app_details.get("status", {}).get("conditions", []),
                    operation_state=app_details.get("status", {}).get("operationState"),
                    observed_at=datetime.now()
                )
                
                result.append(ArgoCDApplicationData(
                    name=name,
                    namespace=namespace,
                    uid=app_details.get("metadata", {}).get("uid", ""),
                    spec=spec,
                    status=status,
                    metadata=app_details.get("metadata", {}),
                    last_sync=datetime.now()
                ))
            
            return result
        except Exception as e:
            logger.error(f"Error getting ArgoCD applications: {e}")
            return []
    
    async def get_application_details(self, app_name: str) -> Optional[ArgoCDApplicationData]:
        """Get detailed information about a specific application"""
        try:
            app_details = await self._run_argocd(["app", "get", app_name])
            
            if not app_details:
                return None
            
            spec = ArgoCDApplicationSpec(
                project=app_details.get("spec", {}).get("project", "default"),
                source=app_details.get("spec", {}).get("source", {}),
                destination=app_details.get("spec", {}).get("destination", {}),
                sync_policy=app_details.get("spec", {}).get("syncPolicy"),
                revision_history_limit=app_details.get("spec", {}).get("revisionHistoryLimit", 3)
            )
            
            status = ArgoCDApplicationStatus(
                health=app_details.get("status", {}).get("health", {}).get("status", "Unknown"),
                sync=app_details.get("status", {}).get("sync", {}).get("status", "Unknown"),
                resources=app_details.get("status", {}).get("resources", []),
                conditions=app_details.get("status", {}).get("conditions", []),
                operation_state=app_details.get("status", {}).get("operationState"),
                observed_at=datetime.now()
            )
            
            return ArgoCDApplicationData(
                name=app_name,
                namespace=app_details.get("metadata", {}).get("namespace", "argocd"),
                uid=app_details.get("metadata", {}).get("uid", ""),
                spec=spec,
                status=status,
                metadata=app_details.get("metadata", {}),
                last_sync=datetime.now()
            )
        except Exception as e:
            logger.error(f"Error getting ArgoCD application details for {app_name}: {e}")
            return None
    
    async def get_argocd_info(self) -> ArgoCDInfo:
        """Get ArgoCD server information"""
        try:
            version_info = await self._run_argocd(["version"])
            apps = await self.get_applications()
            
            healthy_count = sum(1 for app in apps if app.status.health == "Healthy")
            degraded_count = sum(1 for app in apps if app.status.health == "Degraded")
            out_of_sync_count = sum(1 for app in apps if app.status.sync == "OutOfSync")
            
            return ArgoCDInfo(
                version=version_info.get("argocd", "unknown"),
                applications_count=len(apps),
                healthy_apps=healthy_count,
                degraded_apps=degraded_count,
                out_of_sync_apps=out_of_sync_count,
                last_sync=datetime.now()
            )
        except Exception as e:
            logger.error(f"Error getting ArgoCD info: {e}")
            return ArgoCDInfo(
                version="unknown",
                applications_count=0,
                last_sync=datetime.now()
            )
