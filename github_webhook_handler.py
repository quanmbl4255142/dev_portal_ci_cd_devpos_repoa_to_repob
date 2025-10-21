"""
GitHub Webhook Handler để trigger ArgoCD sync ngay lập tức
"""
import asyncio
import logging
import aiohttp
from typing import Dict, Any
import os
from fastapi import FastAPI, Request, HTTPException
import hmac
import hashlib
import json

logger = logging.getLogger(__name__)

class GitHubWebhookHandler:
    """Handler cho GitHub webhooks để trigger ArgoCD sync"""
    
    def __init__(self, argocd_server_url: str, argocd_token: str = None, webhook_secret: str = None):
        self.argocd_server_url = argocd_server_url.rstrip('/')
        self.argocd_token = argocd_token
        self.webhook_secret = webhook_secret
        self.session: aiohttp.ClientSession = None
        # Cho phép cấu hình tên ApplicationSet qua ENV, mặc định 'django-apps'
        self.applicationset_name = os.getenv("ARGOCD_APPLICATIONSET", "django-apps")
        
    async def start_session(self):
        """Start aiohttp session"""
        if not self.session:
            headers = {
                'Content-Type': 'application/json'
            }
            if self.argocd_token:
                headers['Authorization'] = f'Bearer {self.argocd_token}'
            
            # Bỏ kiểm tra SSL để hỗ trợ ArgoCD với self-signed cert (https://127.0.0.1)
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
    
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify GitHub webhook signature"""
        if not self.webhook_secret:
            logger.warning("No webhook secret configured, skipping verification")
            return True
        
        expected_signature = 'sha256=' + hmac.new(
            self.webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    async def trigger_argocd_sync(self, repo_url: str, app_name: str = None) -> bool:
        """Trigger ArgoCD sync for specific application or all apps"""
        try:
            if not self.session:
                await self.start_session()
            
            # Nếu có app_name cụ thể, sync app đó
            if app_name:
                url = f"{self.argocd_server_url}/api/v1/applications/{app_name}/sync"
                payload = {
                    "prune": True,
                    "dryRun": False,
                    "strategy": {
                        "syncStrategy": "apply"
                    }
                }
            else:
                # Sync tất cả applications
                url = f"{self.argocd_server_url}/api/v1/applications/sync"
                payload = {}
            
            async with self.session.post(url, json=payload) as response:
                if response.status in [200, 201]:
                    logger.info(f"Successfully triggered ArgoCD sync for {app_name or 'all apps'}")
                    return True
                else:
                    logger.error(f"ArgoCD sync failed: {response.status} - {await response.text()}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error triggering ArgoCD sync: {e}")
            return False

    async def refresh_applicationset(self) -> bool:
        """Force refresh ApplicationSet để phát hiện app mới nhanh hơn"""
        try:
            if not self.session:
                await self.start_session()
            url = f"{self.argocd_server_url}/api/v1/applicationsets/{self.applicationset_name}/refresh"
            async with self.session.post(url, json={}) as response:
                if response.status in [200, 201]:
                    logger.info(f"ApplicationSet '{self.applicationset_name}' refresh triggered")
                    return True
                else:
                    logger.error(f"ApplicationSet refresh failed: {response.status} - {await response.text()}")
                    return False
        except Exception as e:
            logger.error(f"Error refreshing ApplicationSet: {e}")
            return False
    
    async def handle_push_event(self, payload: Dict[str, Any]) -> bool:
        """Handle GitHub push event"""
        try:
            # Kiểm tra xem có push vào repository_B không
            repo_url = payload.get('repository', {}).get('clone_url', '')
            if 'repository_b_ci_cd_fpt_repob_devops' not in repo_url:
                logger.info(f"Ignoring push event for repo: {repo_url}")
                return False
            
            # Kiểm tra có thay đổi trong thư mục apps/ không
            commits = payload.get('commits', [])
            apps_changed = False
            new_apps = []
            
            for commit in commits:
                added_files = commit.get('added', [])
                modified_files = commit.get('modified', [])
                all_changed_files = added_files + modified_files
                
                for file_path in all_changed_files:
                    if file_path.startswith('apps/'):
                        apps_changed = True
                        # Extract app name from path: apps/app-name/file.yaml
                        parts = file_path.split('/')
                        if len(parts) >= 2:
                            app_name = parts[1]
                            if app_name not in new_apps:
                                new_apps.append(app_name)
            
            if apps_changed:
                logger.info(f"Detected changes in apps/ folder. New/updated apps: {new_apps}")
                
                # Refresh ApplicationSet trước để app mới được tạo ngay
                await self.refresh_applicationset()
                await asyncio.sleep(1)
                
                # Trigger sync cho từng app mới/cập nhật
                for app_name in new_apps:
                    await self.trigger_argocd_sync(repo_url, app_name)
                    await asyncio.sleep(1)  # Frequency limiting
                
                return True
            else:
                logger.info("No changes in apps/ folder, skipping ArgoCD sync")
                return False
                
        except Exception as e:
            logger.error(f"Error handling push event: {e}")
            return False
    
    async def handle_webhook(self, event_type: str, payload: bytes, signature: str = None) -> Dict[str, Any]:
        """Handle GitHub webhook"""
        try:
            # Verify signature
            if not self.verify_webhook_signature(payload, signature or ''):
                raise HTTPException(status_code=401, detail="Invalid webhook signature")
            
            # Parse payload
            data = json.loads(payload.decode('utf-8'))
            
            # Handle different event types
            if event_type == 'push':
                success = await self.handle_push_event(data)
                return {
                    "status": "success" if success else "ignored",
                    "message": "Push event processed" if success else "No relevant changes"
                }
            elif event_type == 'ping':
                return {
                    "status": "success",
                    "message": "Webhook ping received"
                }
            else:
                logger.info(f"Ignoring webhook event type: {event_type}")
                return {
                    "status": "ignored",
                    "message": f"Event type {event_type} not handled"
                }
                
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON payload")
        except Exception as e:
            logger.error(f"Error handling webhook: {e}")
            raise HTTPException(status_code=500, detail=str(e))

# Global webhook handler instance
webhook_handler = None

async def get_webhook_handler() -> GitHubWebhookHandler:
    """Get or create webhook handler instance"""
    global webhook_handler
    
    if webhook_handler is None:
        # Read configuration from environment variables
        # ARGOCD_SERVER: e.g. https://argocd.example.com or https://localhost:8082 (via port-forward)
        # ARGOCD_TOKEN: Bearer token for ArgoCD API
        # GITHUB_WEBHOOK_SECRET: GitHub webhook secret (must match Repo B webhook)
        argocd_url = os.getenv("ARGOCD_SERVER", "")
        argocd_token = os.getenv("ARGOCD_TOKEN", "")
        webhook_secret = os.getenv("GITHUB_WEBHOOK_SECRET", "")
        if not argocd_url:
            logger.warning("ARGOCD_SERVER is not set; ArgoCD sync via webhook will be skipped")
        if not argocd_token:
            logger.warning("ARGOCD_TOKEN is not set; ArgoCD sync may be unauthorized")
        if not webhook_secret:
            logger.warning("GITHUB_WEBHOOK_SECRET is not set; webhook signature verification disabled")
        
        # Fallback minimal defaults for local testing
        if not argocd_url:
            argocd_url = "https://localhost:8082"
        
        webhook_handler = GitHubWebhookHandler(argocd_url, argocd_token, webhook_secret)
        await webhook_handler.start_session()
    
    return webhook_handler

# FastAPI endpoints
async def github_webhook_endpoint(request: Request):
    """GitHub webhook endpoint"""
    try:
        # Get headers
        event_type = request.headers.get('X-GitHub-Event', '')
        signature = request.headers.get('X-Hub-Signature-256', '')
        
        # Get payload
        payload = await request.body()
        
        # Get webhook handler
        handler = await get_webhook_handler()
        
        # Process webhook
        result = await handler.handle_webhook(event_type, payload, signature)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in webhook endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Health check endpoint
async def webhook_health_check():
    """Health check for webhook handler"""
    try:
        handler = await get_webhook_handler()
        return {
            "status": "healthy",
            "argocd_url": handler.argocd_server_url,
            "has_token": bool(handler.argocd_token),
            "has_secret": bool(handler.webhook_secret)
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
