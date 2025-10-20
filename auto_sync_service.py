"""
Auto Sync Service
Tự động lấy dữ liệu từ ArgoCD khi có cập nhật hoặc dữ liệu mới
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import aiohttp
import json
from argo_data_fetcher import ArgoCDDataFetcher
from mongodb_client import get_mongodb_client

logger = logging.getLogger(__name__)

class AutoSyncService:
    """Service tự động sync dữ liệu từ ArgoCD"""
    
    def __init__(self, argocd_server_url: str, argocd_token: str = None, poll_interval: int = 30):
        self.argocd_server_url = argocd_server_url
        self.argocd_token = argocd_token
        self.poll_interval = poll_interval  # seconds
        self.is_running = False
        self.last_sync_time = None
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def start_session(self):
        """Start aiohttp session"""
        if not self.session:
            headers = {
                'Content-Type': 'application/json'
            }
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
    
    async def check_argocd_changes(self) -> bool:
        """Kiểm tra xem có thay đổi nào trong ArgoCD không"""
        try:
            if not self.session:
                await self.start_session()
            
            # Lấy danh sách applications từ ArgoCD
            url = f"{self.argocd_server_url}/api/v1/applications"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    applications = data.get('items', [])
                    
                    # Kiểm tra xem có application nào được cập nhật gần đây không
                    current_time = datetime.utcnow()
                    recent_changes = False
                    
                    for app in applications:
                        # Kiểm tra lastSyncTime
                        last_sync = app.get('status', {}).get('sync', {}).get('syncedAt')
                        if last_sync:
                            try:
                                sync_time = datetime.fromisoformat(last_sync.replace('Z', '+00:00'))
                                if self.last_sync_time is None or sync_time > self.last_sync_time:
                                    recent_changes = True
                                    break
                            except:
                                pass
                        
                        # Kiểm tra creationTimestamp
                        created = app.get('metadata', {}).get('creationTimestamp')
                        if created:
                            try:
                                created_time = datetime.fromisoformat(created.replace('Z', '+00:00'))
                                if self.last_sync_time is None or created_time > self.last_sync_time:
                                    recent_changes = True
                                    break
                            except:
                                pass
                    
                    return recent_changes
                else:
                    logger.error(f"ArgoCD API error: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error checking ArgoCD changes: {e}")
            return False
    
    async def sync_if_changed(self) -> bool:
        """Sync dữ liệu từ ArgoCD vào MongoDB"""
        try:
            logger.info("🔄 Bắt đầu sync dữ liệu từ ArgoCD...")
            
            # Luôn sync dữ liệu từ ArgoCD (không cần kiểm tra thay đổi)
            fetcher = ArgoCDDataFetcher(self.argocd_server_url, self.argocd_token)
            await fetcher.start_session()
            
            try:
                success = await fetcher.sync_applications_to_mongodb()
                if success:
                    self.last_sync_time = datetime.utcnow()
                    logger.info("✅ Sync thành công!")
                    return True
                else:
                    logger.error("❌ Sync thất bại!")
                    return False
            finally:
                await fetcher.close_session()
                
        except Exception as e:
            logger.error(f"Error in sync_if_changed: {e}")
            return False
    
    async def start_auto_sync(self):
        """Bắt đầu auto sync"""
        self.is_running = True
        logger.info(f"🚀 Bắt đầu auto sync với interval {self.poll_interval}s")
        
        while self.is_running:
            try:
                await self.sync_if_changed()
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Error in auto sync loop: {e}")
                await asyncio.sleep(10)  # Wait before retrying
    
    async def stop_auto_sync(self):
        """Dừng auto sync"""
        self.is_running = False
        logger.info("🛑 Dừng auto sync")
        await self.close_session()
    
    async def force_sync(self) -> bool:
        """Force sync ngay lập tức"""
        logger.info("🔄 Force sync được gọi...")
        
        fetcher = ArgoCDDataFetcher(self.argocd_server_url, self.argocd_token)
        await fetcher.start_session()
        
        try:
            success = await fetcher.sync_applications_to_mongodb()
            if success:
                self.last_sync_time = datetime.utcnow()
                logger.info("✅ Force sync thành công!")
            return success
        finally:
            await fetcher.close_session()

# Global auto sync service instance
auto_sync_service = None

async def get_auto_sync_service() -> AutoSyncService:
    """Get or create auto sync service instance"""
    global auto_sync_service
    
    if auto_sync_service is None:
        # ArgoCD URL - Cung cấp URL ArgoCD thật để bật auto sync
        # Thay đổi URL theo môi trường thật của bạn:
        argocd_url = "https://localhost:8082"  # ArgoCD server qua port-forward
        argocd_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJhcmdvY2QiLCJzdWIiOiJhZG1pbjpsb2dpbiIsImV4cCI6MTc2MTAxMzcyMywibmJmIjoxNzYwOTI3MzIzLCJpYXQiOjE3NjA5MjczMjMsImp0aSI6ImMwMDdhZjBjLTgxNTctNDBlYS04YTJjLWIxZTM3MDNjY2IwOCJ9.9c_1Wd6Zh1x0PY0Vs3LZp7ztcNNAoGtjbeO2TXeCg80"
        # argocd_url = "http://127.0.0.1:8090"  # Port 8090 như bạn đang chạy
        # argocd_url = "https://your-argocd-url.com"  # URL thật của bạn
        # argocd_url = None  # Tắt auto sync nếu không có ArgoCD
        if argocd_url:
            auto_sync_service = AutoSyncService(argocd_url, argocd_token, poll_interval=30)
            await auto_sync_service.start_session()
        else:
            # Tạo dummy service khi không có ArgoCD URL
            auto_sync_service = None
    
    return auto_sync_service

async def start_auto_sync():
    """Start auto sync service"""
    service = await get_auto_sync_service()
    if service:
        await service.start_auto_sync()
    else:
        logger.info("⚠️ Auto sync disabled - no ArgoCD URL configured")

async def stop_auto_sync():
    """Stop auto sync service"""
    global auto_sync_service
    if auto_sync_service:
        await auto_sync_service.stop_auto_sync()
        auto_sync_service = None

async def force_sync_now():
    """Force sync ngay lập tức"""
    service = await get_auto_sync_service()
    if service:
        return await service.force_sync()
    else:
        logger.warning("⚠️ Force sync disabled - no ArgoCD URL configured")
        return False
