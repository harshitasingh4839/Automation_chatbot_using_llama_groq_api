import os
from typing import Dict, Optional, Tuple, List
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError, OperationFailure
import streamlit as st


class MongoDBClient:
    def __init__(self):
        self.mongo_uri = os.getenv("MONGODB_URI")
        self.db_name = os.getenv("MONGODB_DB")
        self.client = None
        self.db = None
        self.clients_collection = None
        self.users_collection = None
        self.connected = False  # Track connection status

    def connect(self) -> bool:
        """
        Establishes connection to MongoDB.
        Returns True if successful, False otherwise.
        """
        try:
            self.client = MongoClient(self.mongo_uri)
            self.db = self.client[self.db_name]
            self.clients_collection = self.db["clients"]
            self.users_collection = self.db["users"]
            self.client.admin.command('ping')
            self.connected = True  # Set connected to True on successful connection
            return True
        except ServerSelectionTimeoutError as e:
            st.error(f"MongoDB connection timeout: {str(e)}")
            return False
        except OperationFailure as e:
            st.error(f"Operation failure in MongoDB: {str(e)}")
            return False
        except Exception as e:
            st.error(f"Unexpected error connecting to MongoDB: {str(e)}")
            return False

    def verify_client(self, client_name: str) -> Tuple[bool, Optional[str]]:
        """
        Verify if the client exists and return the client's email if found.
        """
        if not self.connected:
            self.connect()  # Attempt to connect if not already connected
        try:
            client = self.clients_collection.find_one(
                # Check client name case-insensitively 
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
        if not self.connected:
            self.connect()  # Attempt to connect if not already connected
        try:
            clients = self.clients_collection.find({}, {"name": 1})
            return [client["name"] for client in clients if "name" in client]
        except Exception as e:
            print(f"Error retrieving client names: {e}")
            return []
    
    def get_user_details(self, user_email: str) -> Tuple[bool, Optional[object]]:
        """
        Retrieve user details from the users collection using email.
        Returns (True, PaymentReminderDetails instance) if successful, otherwise (False, None).
        """
        if not self.connected:
            self.connect()  # Attempt to connect if not already connected
        try:
            from .response_handlers import PaymentReminderDetails
            
            user_doc = self.users_collection.find_one({"email": user_email})

            # Check if user was found
            if not user_doc:
                return False, None 
            
            # Populate the PaymentReminderDetails dataclass with user details
            user_details = PaymentReminderDetails(
                user_email=user_email,
                user_name=user_doc.get("name"),
                designation=user_doc.get("designation"),
                contact_info=user_doc.get("contact_info")
            )

            return True, user_details
        
        except OperationFailure as e:
            print(f"Error retrieving user details due to operation failure: {e}")
            return False, None
        except Exception as e:
            print(f"Unexpected error retrieving user details: {e}")
            return False, None 

    def close(self):
        if self.client:
            self.client.close()
            self.connected = False  # Reset connection status
