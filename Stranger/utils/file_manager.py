import os
import asyncio
import sqlite3
from typing import Optional, Dict
from pathlib import Path

from pyrogram import Client
from pyrogram.types import Message

from Stranger import userbot, LOGGER, app
from Stranger.utils.database.mongodatabase import (
    add_userbot_two_data,
    update_content_field
)
from Stranger.utils.helper import get_media_data


class FileTaskTracker:
    """SQLite database for tracking file download/upload tasks"""
    
    def __init__(self, db_path: str = "data/file_tasks.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database with required tables"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Download tasks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS download_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_id TEXT NOT NULL,
                content_index INTEGER NOT NULL,
                file_id TEXT NOT NULL,
                media_type TEXT NOT NULL,
                caption TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                error_msg TEXT,
                file_path TEXT,
                file_size INTEGER,
                UNIQUE(content_id, content_index)
            )
        ''')
        
        # Upload tasks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS upload_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_id TEXT NOT NULL,
                content_index INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                error_msg TEXT,
                userbot_msg_id INTEGER,
                UNIQUE(content_id, content_index)
            )
        ''')
        
        # File metadata table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS file_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_id TEXT NOT NULL,
                content_index INTEGER NOT NULL,
                original_file_id TEXT NOT NULL,
                local_file_path TEXT,
                userbot_two_msg_id INTEGER,
                file_size INTEGER,
                media_type TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(content_id, content_index)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def execute_query(self, query: str, params: tuple = (), fetch: bool = False):
        """Execute query with connection management"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(query, params)
            if fetch:
                result = cursor.fetchall()
            else:
                result = cursor.rowcount
            conn.commit()
            return result
        finally:
            conn.close()
    
    def add_download_task(self, content_id: str, content_index: int, file_id: str, 
                         media_type: str, caption: str = None) -> bool:
        """Add new download task"""
        try:
            query = '''
                INSERT OR REPLACE INTO download_tasks 
                (content_id, content_index, file_id, media_type, caption, status, updated_at)
                VALUES (?, ?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP)
            '''
            self.execute_query(query, (content_id, content_index, file_id, media_type, caption))
            return True
        except Exception as e:
            LOGGER(__name__).error(f"Error adding download task: {e}")
            return False
    
    def add_upload_task(self, content_id: str, content_index: int, file_path: str) -> bool:
        """Add new upload task"""
        try:
            query = '''
                INSERT OR REPLACE INTO upload_tasks 
                (content_id, content_index, file_path, status, updated_at)
                VALUES (?, ?, ?, 'pending', CURRENT_TIMESTAMP)
            '''
            self.execute_query(query, (content_id, content_index, file_path))
            return True
        except Exception as e:
            LOGGER(__name__).error(f"Error adding upload task: {e}")
            return False
    
    def update_task_status(self, table: str, task_id: int, status: str, 
                          error_msg: str = None, **kwargs) -> bool:
        """Update task status"""
        try:
            set_clauses = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
            params = [status]
            
            if error_msg:
                set_clauses.append("error_msg = ?")
                params.append(error_msg)
            
            for key, value in kwargs.items():
                set_clauses.append(f"{key} = ?")
                params.append(value)
            
            params.append(task_id)
            
            query = f'''
                UPDATE {table} 
                SET {', '.join(set_clauses)}
                WHERE id = ?
            '''
            self.execute_query(query, tuple(params))
            return True
        except Exception as e:
            LOGGER(__name__).error(f"Error updating task status: {e}")
            return False
    
    def get_pending_tasks(self, table: str) -> list:
        """Get all pending tasks"""
        try:
            query = f'''
                SELECT * FROM {table} 
                WHERE status IN ('pending', 'downloading', 'uploading')
                ORDER BY created_at ASC
            '''
            return self.execute_query(query, fetch=True)
        except Exception as e:
            LOGGER(__name__).error(f"Error getting pending tasks: {e}")
            return []
    
    def add_file_metadata(self, content_id: str, content_index: int, original_file_id: str,
                         media_type: str, file_size: int = None) -> bool:
        """Add file metadata"""
        try:
            query = '''
                INSERT OR REPLACE INTO file_metadata 
                (content_id, content_index, original_file_id, media_type, file_size, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            '''
            self.execute_query(query, (content_id, content_index, original_file_id, media_type, file_size))
            return True
        except Exception as e:
            LOGGER(__name__).error(f"Error adding file metadata: {e}")
            return False
    
    def get_file_metadata(self, content_id: str, content_index: int) -> Optional[Dict]:
        """Get file metadata"""
        try:
            query = '''
                SELECT * FROM file_metadata 
                WHERE content_id = ? AND content_index = ?
            '''
            result = self.execute_query(query, (content_id, content_index), fetch=True)
            if result:
                columns = ['id', 'content_id', 'content_index', 'original_file_id', 'local_file_path',
                          'userbot_two_msg_id', 'file_size', 'media_type', 'status', 'created_at', 'updated_at']
                return dict(zip(columns, result[0]))
            return None
        except Exception as e:
            LOGGER(__name__).error(f"Error getting file metadata: {e}")
            return None


class FileManager:
    """Main file download/upload manager"""
    
    def __init__(self, storage_path: str = "data/files"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.tracker = FileTaskTracker()
        self.active_tasks = set()
        self.backup_tasks = set()  # Track active backup tasks
        
    async def process_file(self, message: Message, content_id: str, content_index: int) -> bool:
        """Main entry point for processing files from listener"""
        try:
            # Check if task is already active
            if self.is_task_active(content_id, content_index):
                LOGGER(__name__).info(f"Task already active for {content_id}_{content_index}")
                return True
            
            media_data = get_media_data(message)
            if not media_data:
                return False
            
            file_id = media_data['file_id']
            media_type = media_data['type']
            caption = message.caption or ""
            
            # Add to tracker
            self.tracker.add_download_task(content_id, content_index, file_id, media_type, caption)
            self.tracker.add_file_metadata(content_id, content_index, file_id, media_type)
            
            # Start async download task
            self.add_active_task(content_id, content_index)
            asyncio.create_task(self._download_and_upload_file(content_id, content_index, file_id, media_type, caption))
            
            return True
            
        except Exception as e:
            LOGGER(__name__).error(f"Error processing file: {e}")
            return False
    
    async def _download_and_upload_file(self, content_id: str, content_index: int, 
                                      file_id: str, media_type: str, caption: str):
        """Download file and upload to userbot.two"""
        try:
            # Download file
            file_path = await self._download_file(content_id, content_index, file_id)
            if not file_path:
                return False
            
            # Upload to userbot.two
            success = await self._upload_to_userbot_two(content_id, content_index, file_path, caption)
            
            if success:
                # Clean up local file
                try:
                    os.remove(file_path)
                except:
                    pass
                
                LOGGER(__name__).info(f"Successfully processed file for {content_id}_{content_index}")
            
            return success
            
        except Exception as e:
            LOGGER(__name__).error(f"Error in download/upload process: {e}")
            return False
        finally:
            self.remove_active_task(content_id, content_index)
    
    async def _download_file(self, content_id: str, content_index: int, file_id: str) -> Optional[str]:
        """Download file from Telegram using generic method"""
        try:
            # Get task ID for tracking
            download_tasks = self.tracker.get_pending_tasks('download_tasks')
            task_id = None
            for task in download_tasks:
                if task[1] == content_id and task[2] == content_index:
                    task_id = task[0]
                    break
            
            if not task_id:
                return None
            
            # Use generic download method - let Pyrogram handle everything
            file_path = await self._download_file_generic(
                userbot.one, file_id, task_id, 'download_tasks'
            )
            
            return file_path
            
        except Exception as e:
            LOGGER(__name__).error(f"Error downloading file: {e}")
            return None
    
    async def _upload_to_userbot_two(self, content_id: str, content_index: int, 
                                   file_path: str, caption: str) -> bool:
        """Upload file to userbot.two saved messages using generic method"""
        try:
            # Add upload task
            self.tracker.add_upload_task(content_id, content_index, file_path)
            
            # Get upload task ID and media type
            upload_tasks = self.tracker.get_pending_tasks('upload_tasks')
            task_id = None
            for task in upload_tasks:
                if task[1] == content_id and task[2] == content_index:
                    task_id = task[0]
                    break
            
            if not task_id:
                return False
            
            # Get media type from file metadata
            metadata = self.tracker.get_file_metadata(content_id, content_index)
            media_type = metadata.get('media_type') if metadata else None
            
            # Use generic upload method with proper media type
            sent_message = await self._upload_file_generic(
                userbot.two, "me", file_path, caption, media_type, task_id, 'upload_tasks'
            )
            
            if sent_message:
                # Update MongoDB with userbot_two_data
                await add_userbot_two_data(content_id, content_index, sent_message.id, userbot.two.me.id)
                
                # Update file metadata
                metadata = self.tracker.get_file_metadata(content_id, content_index)
                if metadata:
                    self.tracker.execute_query('''
                        UPDATE file_metadata 
                        SET userbot_two_msg_id = ?, status = 'uploaded', updated_at = CURRENT_TIMESTAMP
                        WHERE content_id = ? AND content_index = ?
                    ''', (sent_message.id, content_id, content_index))
                
                return True
            
            return False
            
        except Exception as e:
            LOGGER(__name__).error(f"Error uploading to userbot.two: {e}")
            return False
    
    async def get_file_from_userbot_two(self, content_id: str, content_index: int) -> Optional[str]:
        """Download file from userbot.two for backup purposes (non-blocking)"""
        try:
            # Get file metadata
            metadata = self.tracker.get_file_metadata(content_id, content_index)
            if not metadata or not metadata.get('userbot_two_msg_id'):
                return None

            msg = userbot.two.get_messages(chat_id="me", message_ids=metadata['userbot_two_msg_id'])
            media_data = get_media_data(msg)
            
            # Use generic download method - let Pyrogram handle everything
            file_path = await self._download_file_generic(
                userbot.two, media_data['file_id']
            )
            
            return file_path
            
        except Exception as e:
            LOGGER(__name__).error(f"Error downloading from userbot.two: {e}")
            return None
    
    async def upload_backup_to_userbot_one(self, content_id: str, content_index: int, 
                                         file_path: str, caption: str = None, media_type: str = None) -> Optional[Message]:
        """Upload backup file to userbot.one using generic method"""
        try:
            # Use generic upload method with proper media type
            sent_message = await self._upload_file_generic(
                userbot.one, "me", file_path, caption or "", media_type
            )
            
            # Clean up temp file
            try:
                os.remove(file_path)
            except:
                pass
            
            return sent_message
            
        except Exception as e:
            LOGGER(__name__).error(f"Error uploading backup to userbot.one: {e}")
            return None
    
    def is_backup_processing(self, content_id: str) -> bool:
        """Check if backup is being processed for this content"""
        # Check if any content_index for this content_id is being processed
        for task_key in self.backup_tasks:
            if task_key.startswith(f"{content_id}_"):
                return True
        return False
    
    async def start_backup_processing(self, content_id: str, file_data: dict):
        """Start background backup processing"""
        try:
            LOGGER(__name__).info(f"Starting backup processing for {content_id}")
            
            contents = file_data.get('contents', [])
            for content_index, content in enumerate(contents):
                # Check if backup task is already active
                if self.is_task_active(content_id, content_index, "backup"):
                    continue
                
                userbot_two_data = content.get('userbot_two_data', {})
                if not userbot_two_data or not userbot_two_data.get('msg_id'):
                    continue
                
                # Start backup task
                self.add_active_task(content_id, content_index, "backup")
                asyncio.create_task(self._process_single_backup(content_id, content_index, content))
            
        except Exception as e:
            LOGGER(__name__).error(f"Error starting backup processing: {e}")
    
    async def _process_single_backup(self, content_id: str, content_index: int, content: dict):
        """Process single file backup"""
        try:
            # Download from userbot.two
            file_path = await self.get_file_from_userbot_two(content_id, content_index)
            if not file_path:
                return False
            
            # Get media type from file metadata
            metadata = self.tracker.get_file_metadata(content_id, content_index)
            media_type = metadata.get('media_type') if metadata else None
            
            # Upload to userbot.one
            userbot_one_data = content.get('userbot_one_data', {})
            caption = userbot_one_data.get('caption', "")
            
            sent_msg = await self.upload_backup_to_userbot_one(content_id, content_index, file_path, caption, media_type)
            
            if sent_msg:
                # Get media data from the uploaded message
                saved_media_data = get_media_data(sent_msg)
                
                if saved_media_data:
                    # Update MongoDB userbot_one_data with new backup file details
                    # This updates the existing userbot_one_data in the contents array
                    await update_content_field(
                        content_id, 
                        f'contents.{content_index}.userbot_one_data',
                        {
                            "file_id": saved_media_data['file_id'],
                            "media_type": saved_media_data['type'],
                            "caption": caption,
                            "msg_id": sent_msg.id,
                            "user_id": userbot.one.me.id
                        }
                    )
                    
                    # Update caption with content_index and send to managed bots
                    updated_caption = caption.replace("content_index=PLACEHOLDER", f"content_index={content_index}")
                    
                    # Send to managed bots
                    for bot_token, bot_info in app.managed_bots.items():
                        try:
                            await userbot.one.send_cached_media(
                                chat_id=bot_info['username'],
                                file_id=saved_media_data['file_id'],
                                caption=updated_caption
                            )
                            await asyncio.sleep(0.2)  # Rate limiting
                        except Exception as e:
                            LOGGER(__name__).error(f"Error sending backup to bot {bot_info['username']}: {e}")
                            continue
                    
                    LOGGER(__name__).info(f"Backup processed, MongoDB updated, and sent to managed bots for {content_id}_{content_index}")
                else:
                    LOGGER(__name__).warning(f"Could not get media data from backup message for {content_id}_{content_index}")
                
                return True
            
            return False
            
        except Exception as e:
            LOGGER(__name__).error(f"Error processing backup for {content_id}_{content_index}: {e}")
            return False
        finally:
            self.remove_active_task(content_id, content_index, "backup")
    
    async def resume_pending_tasks(self):
        """Resume pending tasks after bot restart"""
        try:
            LOGGER(__name__).info("Resuming pending file tasks...")
            
            # Resume download tasks
            download_tasks = self.tracker.get_pending_tasks('download_tasks')
            for task in download_tasks:
                task_id, content_id, content_index, file_id, media_type, caption = task[:6]
                
                # Skip if already active
                if self.is_task_active(content_id, content_index):
                    continue
                
                self.add_active_task(content_id, content_index)
                asyncio.create_task(self._download_and_upload_file(content_id, content_index, file_id, media_type, caption))
            
            # Resume upload tasks
            upload_tasks = self.tracker.get_pending_tasks('upload_tasks')
            for task in upload_tasks:
                task_id, content_id, content_index, file_path = task[:4]
                
                # Check if file still exists
                if not os.path.exists(file_path):
                    self.tracker.update_task_status('upload_tasks', task_id, 'failed', 'File not found')
                    continue
                
                # Skip if already active
                if self.is_task_active(content_id, content_index):
                    continue
                
                self.add_active_task(content_id, content_index)
                asyncio.create_task(self._upload_to_userbot_two(content_id, content_index, file_path, ""))
            
            LOGGER(__name__).info("Pending tasks resumed successfully")
            
        except Exception as e:
            LOGGER(__name__).error(f"Error resuming pending tasks: {e}")
    
    async def _download_file_generic(
            self, 
            client: Client, 
            file_id: str,
            task_id: int = None, 
            table: str = None
            ) -> Optional[str]:
        """Generic method to download file from any source with proper extension"""
        try:
            if task_id and table:
                self.tracker.update_task_status(table, task_id, 'downloading')
            
            # Let Pyrogram auto-download with proper filename and extension
            downloaded_path = await client.download_media(file_id)
            
            if task_id and table and downloaded_path:
                file_size = Path(downloaded_path).stat().st_size if Path(downloaded_path).exists() else 0
                self.tracker.update_task_status(table, task_id, 'downloaded', 
                                              file_path=downloaded_path, file_size=file_size)
            
            return downloaded_path
            
        except Exception as e:
            LOGGER(__name__).error(f"Error downloading file: {e}")
            if task_id and table:
                self.tracker.update_task_status(table, task_id, 'failed', str(e))
            return None
    
    async def _upload_file_generic(self, client: Client, target_chat: str, file_path: str, 
                                 caption: str, media_type: str = None, task_id: int = None, table: str = None) -> Optional[Message]:
        """Generic method to upload file to any destination using proper media type"""
        try:
            if task_id and table:
                self.tracker.update_task_status(table, task_id, 'uploading')
            
            # Send using appropriate method based on media type
            if media_type == "photo":
                sent_message = await client.send_photo(
                    chat_id=target_chat,
                    photo=file_path,
                    caption=caption
                )
            elif media_type == "video":
                sent_message = await client.send_video(
                    chat_id=target_chat,
                    video=file_path,
                    caption=caption
                )
            elif media_type in ["audio", "voice"]:
                sent_message = await client.send_audio(
                    chat_id=target_chat,
                    audio=file_path,
                    caption=caption
                )
            else:
                # Default to document for unknown types or actual documents
                sent_message = await client.send_document(
                    chat_id=target_chat,
                    document=file_path,
                    caption=caption
                )
            
            if task_id and table:
                self.tracker.update_task_status(table, task_id, 'uploaded', 
                                              userbot_msg_id=sent_message.id)
            
            return sent_message
            
        except Exception as e:
            LOGGER(__name__).error(f"Error uploading file: {e}")
            if task_id and table:
                self.tracker.update_task_status(table, task_id, 'failed', str(e))
            return None
    
    def is_task_active(self, content_id: str, content_index: int, task_type: str = "normal") -> bool:
        """Check if task is already active"""
        task_key = f"{content_id}_{content_index}"
        if task_type == "backup":
            return task_key in self.backup_tasks
        return task_key in self.active_tasks
    
    def add_active_task(self, content_id: str, content_index: int, task_type: str = "normal"):
        """Add task to active set"""
        task_key = f"{content_id}_{content_index}"
        if task_type == "backup":
            self.backup_tasks.add(task_key)
        else:
            self.active_tasks.add(task_key)
    
    def remove_active_task(self, content_id: str, content_index: int, task_type: str = "normal"):
        """Remove task from active set"""
        task_key = f"{content_id}_{content_index}"
        if task_type == "backup":
            self.backup_tasks.discard(task_key)
        else:
            self.active_tasks.discard(task_key)
    
    def get_backup_status(self, content_id: str) -> dict:
        """Get backup processing status"""
        status = {
            "is_processing": self.is_backup_processing(content_id),
            "total_files": 0,
            "processed_files": 0,
            "failed_files": 0
        }
        
        try:
            # Get file metadata to count files
            query = '''
                SELECT COUNT(*) FROM file_metadata 
                WHERE content_id = ? AND userbot_two_msg_id IS NOT NULL
            '''
            result = self.tracker.execute_query(query, (content_id,), fetch=True)
            if result:
                status["total_files"] = result[0][0]
                
            if not status["is_processing"] and status["total_files"] > 0:
                status["processed_files"] = status["total_files"]
            
        except Exception as e:
            LOGGER(__name__).error(f"Error getting backup status: {e}")
        
        return status


# Global file manager instance
file_manager = FileManager()
