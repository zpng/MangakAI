"""
Cloud storage integration for MangakAI
Supports AWS S3, Alibaba Cloud OSS, and local storage fallback
"""
import os
import logging
from typing import Optional, Union
from PIL import Image
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import io

logger = logging.getLogger(__name__)

class CloudStorageManager:
    """
    Cloud storage manager with multiple provider support
    """
    
    def __init__(self):
        self.storage_type = os.getenv("STORAGE_TYPE", "local")  # local, s3, oss
        self.local_storage_path = os.getenv("LOCAL_STORAGE_PATH", "data/cloud_storage")
        
        # AWS S3 configuration
        self.s3_bucket = os.getenv("S3_BUCKET")
        self.s3_region = os.getenv("AWS_REGION", "ap-southeast-1")
        self.s3_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        self.s3_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        
        # CDN configuration
        self.cdn_base_url = os.getenv("CDN_BASE_URL", "")
        
        # Initialize storage client
        self._init_storage_client()
    
    def _init_storage_client(self):
        """Initialize storage client based on configuration"""
        if self.storage_type == "s3":
            try:
                self.s3_client = boto3.client(
                    's3',
                    region_name=self.s3_region,
                    aws_access_key_id=self.s3_access_key,
                    aws_secret_access_key=self.s3_secret_key
                )
                logger.info("S3 client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize S3 client: {str(e)}")
                self.storage_type = "local"  # Fallback to local storage
        
        elif self.storage_type == "local":
            # Ensure local storage directory exists
            os.makedirs(self.local_storage_path, exist_ok=True)
            logger.info(f"Local storage initialized at: {self.local_storage_path}")
    
    def upload_file(self, local_file_path: str, cloud_key: str, optimize_image: bool = True) -> Optional[str]:
        """
        Upload file to cloud storage
        
        Args:
            local_file_path: Path to local file
            cloud_key: Key/path in cloud storage
            optimize_image: Whether to optimize image before upload
            
        Returns:
            Public URL of uploaded file or None if failed
        """
        try:
            # Optimize image if requested and file is an image
            if optimize_image and self._is_image_file(local_file_path):
                local_file_path = self._optimize_image(local_file_path)
            
            if self.storage_type == "s3":
                return self._upload_to_s3(local_file_path, cloud_key)
            elif self.storage_type == "local":
                return self._upload_to_local(local_file_path, cloud_key)
            else:
                logger.error(f"Unsupported storage type: {self.storage_type}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to upload file {local_file_path}: {str(e)}")
            return None
    
    def _upload_to_s3(self, local_file_path: str, cloud_key: str) -> Optional[str]:
        """Upload file to AWS S3"""
        try:
            # Determine content type
            content_type = self._get_content_type(local_file_path)
            
            # Upload file
            self.s3_client.upload_file(
                local_file_path,
                self.s3_bucket,
                cloud_key,
                ExtraArgs={
                    'ContentType': content_type,
                    'ACL': 'public-read'  # Make file publicly accessible
                }
            )
            
            # Generate public URL
            if self.cdn_base_url:
                public_url = f"{self.cdn_base_url}/{cloud_key}"
            else:
                public_url = f"https://{self.s3_bucket}.s3.{self.s3_region}.amazonaws.com/{cloud_key}"
            
            logger.info(f"Successfully uploaded to S3: {cloud_key}")
            return public_url
            
        except ClientError as e:
            logger.error(f"S3 upload failed: {str(e)}")
            return None
        except NoCredentialsError:
            logger.error("S3 credentials not found")
            return None
    
    def _upload_to_local(self, local_file_path: str, cloud_key: str) -> Optional[str]:
        """Upload file to local storage (fallback)"""
        try:
            # Create destination path
            dest_path = os.path.join(self.local_storage_path, cloud_key)
            dest_dir = os.path.dirname(dest_path)
            os.makedirs(dest_dir, exist_ok=True)
            
            # Copy file
            import shutil
            shutil.copy2(local_file_path, dest_path)
            
            # Generate local URL (relative to static files)
            relative_path = os.path.relpath(dest_path, "data")
            public_url = f"/static/{relative_path}"
            
            logger.info(f"Successfully uploaded to local storage: {cloud_key}")
            return public_url
            
        except Exception as e:
            logger.error(f"Local upload failed: {str(e)}")
            return None
    
    def download_file(self, cloud_key: str, local_file_path: str) -> bool:
        """
        Download file from cloud storage
        
        Args:
            cloud_key: Key/path in cloud storage
            local_file_path: Local path to save file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.storage_type == "s3":
                return self._download_from_s3(cloud_key, local_file_path)
            elif self.storage_type == "local":
                return self._download_from_local(cloud_key, local_file_path)
            else:
                logger.error(f"Unsupported storage type: {self.storage_type}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to download file {cloud_key}: {str(e)}")
            return False
    
    def _download_from_s3(self, cloud_key: str, local_file_path: str) -> bool:
        """Download file from AWS S3"""
        try:
            self.s3_client.download_file(self.s3_bucket, cloud_key, local_file_path)
            logger.info(f"Successfully downloaded from S3: {cloud_key}")
            return True
        except ClientError as e:
            logger.error(f"S3 download failed: {str(e)}")
            return False
    
    def _download_from_local(self, cloud_key: str, local_file_path: str) -> bool:
        """Download file from local storage"""
        try:
            source_path = os.path.join(self.local_storage_path, cloud_key)
            if not os.path.exists(source_path):
                logger.error(f"Local file not found: {source_path}")
                return False
            
            import shutil
            shutil.copy2(source_path, local_file_path)
            logger.info(f"Successfully downloaded from local storage: {cloud_key}")
            return True
        except Exception as e:
            logger.error(f"Local download failed: {str(e)}")
            return False
    
    def delete_file(self, cloud_key: str) -> bool:
        """
        Delete file from cloud storage
        
        Args:
            cloud_key: Key/path in cloud storage
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.storage_type == "s3":
                return self._delete_from_s3(cloud_key)
            elif self.storage_type == "local":
                return self._delete_from_local(cloud_key)
            else:
                logger.error(f"Unsupported storage type: {self.storage_type}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete file {cloud_key}: {str(e)}")
            return False
    
    def _delete_from_s3(self, cloud_key: str) -> bool:
        """Delete file from AWS S3"""
        try:
            self.s3_client.delete_object(Bucket=self.s3_bucket, Key=cloud_key)
            logger.info(f"Successfully deleted from S3: {cloud_key}")
            return True
        except ClientError as e:
            logger.error(f"S3 delete failed: {str(e)}")
            return False
    
    def _delete_from_local(self, cloud_key: str) -> bool:
        """Delete file from local storage"""
        try:
            file_path = os.path.join(self.local_storage_path, cloud_key)
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Successfully deleted from local storage: {cloud_key}")
            return True
        except Exception as e:
            logger.error(f"Local delete failed: {str(e)}")
            return False
    
    def _optimize_image(self, image_path: str) -> str:
        """
        Optimize image for web delivery
        
        Args:
            image_path: Path to original image
            
        Returns:
            Path to optimized image
        """
        try:
            # Create optimized filename
            base_name, ext = os.path.splitext(image_path)
            optimized_path = f"{base_name}_optimized.webp"
            
            # Open and optimize image
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Resize if too large (max 2048px on longest side)
                max_size = 2048
                if max(img.size) > max_size:
                    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                
                # Save as WebP with optimization
                img.save(
                    optimized_path,
                    'WEBP',
                    quality=85,
                    optimize=True,
                    method=6
                )
            
            logger.info(f"Image optimized: {image_path} -> {optimized_path}")
            return optimized_path
            
        except Exception as e:
            logger.warning(f"Image optimization failed, using original: {str(e)}")
            return image_path
    
    def _is_image_file(self, file_path: str) -> bool:
        """Check if file is an image"""
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'}
        _, ext = os.path.splitext(file_path.lower())
        return ext in image_extensions
    
    def _get_content_type(self, file_path: str) -> str:
        """Get MIME content type for file"""
        _, ext = os.path.splitext(file_path.lower())
        
        content_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.pdf': 'application/pdf',
            '.txt': 'text/plain',
            '.json': 'application/json'
        }
        
        return content_types.get(ext, 'application/octet-stream')

# Global storage manager instance
storage_manager = CloudStorageManager()

# Convenience functions
def upload_to_cloud_storage(local_file_path: str, cloud_key: str, optimize_image: bool = True) -> Optional[str]:
    """Upload file to cloud storage"""
    return storage_manager.upload_file(local_file_path, cloud_key, optimize_image)

def download_from_cloud_storage(cloud_key: str, local_file_path: str) -> bool:
    """Download file from cloud storage"""
    return storage_manager.download_file(cloud_key, local_file_path)

def delete_from_cloud_storage(cloud_key: str) -> bool:
    """Delete file from cloud storage"""
    return storage_manager.delete_file(cloud_key)