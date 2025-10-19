"""
MongoDB Client for Dev Portal Service
Handles connection and operations with MongoDB
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class MongoDBClient:
    """MongoDB client for handling ArgoCD application data"""
    
    def __init__(self, connection_string: str, database_name: str = "argocd_apps"):
        self.connection_string = connection_string
        self.database_name = database_name
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None
        self.collection = None
        
    async def connect(self):
        """Connect to MongoDB"""
        try:
            self.client = AsyncIOMotorClient(
                self.connection_string,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=5000
            )
            
            # Test connection
            await self.client.admin.command('ping')
            self.db = self.client[self.database_name]
            self.collection = self.db.applications
            
            # Create indexes for better performance
            await self.collection.create_index("name", unique=True)
            await self.collection.create_index("gitRepo.url")
            await self.collection.create_index("updatedAt")
            
            logger.info(f"Connected to MongoDB database: {self.database_name}")
            return True
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to MongoDB: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")
    
    async def upsert_application(self, app_data: Dict[str, Any]) -> bool:
        """
        Insert or update application data
        Returns True if successful, False otherwise
        """
        try:
            if self.collection is None:
                logger.error("MongoDB not connected")
                return False
            
            # Ensure required fields
            if not app_data.get('name'):
                logger.error("Application name is required")
                return False
            
            # Add timestamps
            now = datetime.utcnow()
            app_data['updatedAt'] = now
            
            # If this is a new application, set createdAt
            if not app_data.get('createdAt'):
                app_data['createdAt'] = now
            
            # Use upsert to insert or update
            result = await self.collection.replace_one(
                {"name": app_data['name']},
                app_data,
                upsert=True
            )
            
            if result.upserted_id or result.modified_count > 0:
                logger.info(f"Successfully upserted application: {app_data['name']}")
                return True
            else:
                logger.warning(f"No changes made to application: {app_data['name']}")
                return True
                
        except Exception as e:
            logger.error(f"Error upserting application {app_data.get('name', 'unknown')}: {e}")
            return False
    
    async def get_all_applications(self) -> List[Dict[str, Any]]:
        """Get all applications from MongoDB"""
        try:
            if self.collection is None:
                logger.error("MongoDB not connected")
                return []
            
            cursor = self.collection.find({}).sort("updatedAt", -1)
            applications = await cursor.to_list(length=None)
            
            # Convert ObjectId to string for JSON serialization
            for app in applications:
                app['_id'] = str(app['_id'])
            
            logger.info(f"Retrieved {len(applications)} applications from MongoDB")
            return applications
            
        except Exception as e:
            logger.error(f"Error retrieving applications: {e}")
            return []
    
    async def get_application_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get specific application by name"""
        try:
            if self.collection is None:
                logger.error("MongoDB not connected")
                return None
            
            app = await self.collection.find_one({"name": name})
            if app:
                app['_id'] = str(app['_id'])
            
            return app
            
        except Exception as e:
            logger.error(f"Error retrieving application {name}: {e}")
            return None
    
    async def delete_application(self, name: str) -> bool:
        """Delete application by name"""
        try:
            if self.collection is None:
                logger.error("MongoDB not connected")
                return False
            
            result = await self.collection.delete_one({"name": name})
            
            if result.deleted_count > 0:
                logger.info(f"Successfully deleted application: {name}")
                return True
            else:
                logger.warning(f"Application not found: {name}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting application {name}: {e}")
            return False
    
    async def get_applications_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get applications by health status"""
        try:
            if self.collection is None:
                logger.error("MongoDB not connected")
                return []
            
            cursor = self.collection.find({"healthStatus": status}).sort("updatedAt", -1)
            applications = await cursor.to_list(length=None)
            
            for app in applications:
                app['_id'] = str(app['_id'])
            
            return applications
            
        except Exception as e:
            logger.error(f"Error retrieving applications by status {status}: {e}")
            return []
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get dashboard statistics"""
        try:
            if self.collection is None:
                logger.error("MongoDB not connected")
                return {}
            
            pipeline = [
                {
                    "$group": {
                        "_id": None,
                        "totalApplications": {"$sum": 1},
                        "healthyApplications": {
                            "$sum": {"$cond": [{"$eq": ["$healthStatus", "Healthy"]}, 1, 0]}
                        },
                        "degradedApplications": {
                            "$sum": {"$cond": [{"$eq": ["$healthStatus", "Degraded"]}, 1, 0]}
                        },
                        "failedApplications": {
                            "$sum": {"$cond": [{"$eq": ["$healthStatus", "Failed"]}, 1, 0]}
                        },
                        "totalServices": {
                            "$sum": {
                                "$cond": [
                                    {"$and": [{"$ne": ["$services", None]}, {"$isArray": "$services"}]},
                                    {"$size": "$services"},
                                    0
                                ]
                            }
                        },
                        "healthyServices": {
                            "$sum": {
                                "$cond": [
                                    {"$and": [{"$ne": ["$services", None]}, {"$isArray": "$services"}]},
                                    {
                                        "$size": {
                                            "$filter": {
                                                "input": "$services",
                                                "cond": {"$eq": ["$$this.status", "Running"]}
                                            }
                                        }
                                    },
                                    0
                                ]
                            }
                        }
                    }
                }
            ]
            
            result = await self.collection.aggregate(pipeline).to_list(1)
            
            if result:
                stats = result[0]
                del stats['_id']  # Remove MongoDB internal field
                
                # Calculate health percentage
                total = stats.get('totalApplications', 0)
                healthy = stats.get('healthyApplications', 0)
                stats['healthPercentage'] = round((healthy / total * 100) if total > 0 else 0, 1)
                
                return stats
            else:
                return {
                    "totalApplications": 0,
                    "healthyApplications": 0,
                    "degradedApplications": 0,
                    "failedApplications": 0,
                    "totalServices": 0,
                    "healthyServices": 0,
                    "healthPercentage": 0
                }
                
        except Exception as e:
            logger.error(f"Error calculating statistics: {e}")
            return {}

# Global MongoDB client instance
mongodb_client = None

async def get_mongodb_client() -> MongoDBClient:
    """Get or create MongoDB client instance"""
    global mongodb_client
    
    if mongodb_client is None:
        connection_string = os.getenv(
            "MONGODB_URL", 
            "mongodb+srv://quandeptrai5122004_db_user:DG6SzehMsGT7OosW@mongotestk8s.wssdzb8.mongodb.net/?retryWrites=true&w=majority&appName=mongotestk8s"
        )
        
        mongodb_client = MongoDBClient(connection_string)
        await mongodb_client.connect()
    
    return mongodb_client
