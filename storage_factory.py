import os
from dynamodb_storage import DynamoDBStorage
from sqlite_storage import SQLiteStorage
from storage_interface import StorageInterface
from init_db import init_db

class StorageFactory:
    @staticmethod
    def create_storage() -> StorageInterface:
        storage_type = os.getenv("STORAGE_TYPE", "sqlite").lower()

        if storage_type == "dynamodb":
            return DynamoDBStorage()
        elif storage_type == "sqlite":
            init_db()
            return SQLiteStorage()
        else:
            raise ValueError(f"Unsupported storage type: {storage_type}")