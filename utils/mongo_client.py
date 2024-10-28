import os
from typing import Dict, Optional, Tuple, List
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError, OperationFailure
import streamlit as st

class MongoDBClient:
    def __init__(self):
        self.mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
        self.db_name = os.getenv("MONGODB_DB", "assistant_db")
        self.collection_name = "clients"
        self.client = None
        self.db = None
        self.collection = None

    def connect(self):
        try:
            self.client = MongoClient(self.mongo_uri)
            self.db = self.client[self.db_name]
            self.collection = self.db[self.collection_name]
            self.client.admin.command('ping')
            return True
        except ConnectionError as e:
            st.error(f"Failed to connect to MongoDB: {str(e)}")
            return False

    def verify_client(self, client_name: str) -> Tuple[bool, Optional[str]]:
        try:
            client = self.collection.find_one(
                {"name": {"$regex": f"^{client_name}$", "$options": "i"}}
            )
            if client:
                return True, client.get("email")
            return False, None
        except OperationFailure as e:
            st.error(f"Database operation failed: {str(e)}")
            return False, None
        
    def get_all_client_names(self) -> List[str]:
        """
        Retrieve all client names from the database.
        Returns a list of client names.
        """
        try:
            # Find all clients and extract their names
            clients = self.db.clients.find({},{"name":1})
            return [client["name"] for client in clients if "name" in client]
        except Exception as e :
            print(f"Error retrieving cleint names: {e}")
            return []
    
        

    def close(self):
        if self.client:
            self.client.close()