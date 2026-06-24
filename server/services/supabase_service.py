import hashlib
import os
import random
import time
from typing import Dict, Any, Optional
from supabase import create_client, Client
from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

class SupabaseService:
    """Manages server registration, pairing codes, and pairing state in Supabase."""
    
    def __init__(self):
        self.url = settings.SUPABASE_URL
        self.key = settings.SUPABASE_SECRET_KEY or settings.SUPABASE_SERVICE_ROLE_KEY
        self.client: Optional[Client] = None
        self.is_initialized = False
        
    def initialize(self) -> bool:
        if self.is_initialized:
            return True
        try:
            if not self.url or not self.key:
                logger.error("Supabase URL or Secret Key missing in settings.")
                return False
            self.client = create_client(self.url, self.key)
            self.is_initialized = True
            logger.info("SupabaseService initialized successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            return False

    def register_server_device(self, user_id: str) -> bool:
        """Registers this server device in the devices table if it doesn't exist."""
        if not self.initialize() or not self.client:
            return False
            
        try:
            device_id = settings.SERVER_DEVICE_ID
            device_name = settings.SERVER_DEVICE_NAME
            
            # Upsert device
            data = {
                "id": device_id,
                "user_id": user_id,
                "type": "server",
                "name": device_name
            }
            
            self.client.table("devices").upsert(data).execute()
            logger.info(f"Registered server device {device_id} in Supabase for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error registering server device: {e}")
            return False

    def generate_pairing_code(self, user_id: str) -> Optional[str]:
        """Generates a 6-digit pairing code, hashes it with a salt, and saves it."""
        if not self.initialize() or not self.client:
            return None
            
        try:
            # First, register the server device to ensure foreign keys pass
            if not self.register_server_device(user_id):
                return None
                
            code = f"{random.randint(0, 999999):06d}"
            salt = os.urandom(16).hex()
            
            # Hash code + salt
            hasher = hashlib.sha256()
            hasher.update((code + salt).encode('utf-8'))
            hashed_code = hasher.hexdigest()
            
            # 5 minutes expiration
            expires_at = int(time.time()) + 300
            
            # Save code session in device_pairing_codes
            device_id = settings.SERVER_DEVICE_ID
            
            # Delete any existing active pairing codes for this device to clean up
            self.client.table("device_pairing_codes").delete().eq("device_id", device_id).execute()
            
            data = {
                "device_id": device_id,
                "hashed_code": hashed_code,
                "salt": salt,
                "expires_at": expires_at,
                "used": False
            }
            
            self.client.table("device_pairing_codes").insert(data).execute()
            logger.info(f"Generated new pairing code for device {device_id} expiring in 5 minutes.")
            return code
            
        except Exception as e:
            logger.error(f"Error generating pairing code: {e}")
            return None

    def check_pairing_status(self) -> Dict[str, Any]:
        """Checks if there is an active pair in device_pairs for this server."""
        if not self.initialize() or not self.client:
            return {"status": "uninitialized", "pair_id": None}
            
        try:
            device_id = settings.SERVER_DEVICE_ID
            
            # Query active pair
            response = self.client.table("device_pairs")\
                .select("*")\
                .eq("server_device_id", device_id)\
                .eq("status", "active")\
                .execute()
                
            pairs = response.data
            if pairs and len(pairs) > 0:
                pair = pairs[0]
                return {
                    "status": "paired",
                    "pair_id": pair["id"],
                    "mobile_device_id": pair["mobile_device_id"],
                    "user_id": pair["user_id"]
                }
            
            return {"status": "unpaired", "pair_id": None}
        except Exception as e:
            logger.error(f"Error checking pairing status: {e}")
            return {"status": "error", "message": str(e)}
