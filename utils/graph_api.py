import os
from datetime import datetime
import httpx
import streamlit as st
from msal import ConfidentialClientApplication
from typing import Optional

class MSGraphAPI:
    def __init__(self):
        self.client_id = os.getenv("AZURE_CLIENT_ID")
        self.client_secret = os.getenv("AZURE_CLIENT_SECRET")
        self.tenant_id = os.getenv("AZURE_TENANT_ID")
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.scope = ["https://graph.microsoft.com/.default"]
        self.endpoint = "https://graph.microsoft.com/v1.0"
        
    def get_access_token(self) -> Optional[str]:
        """Get Microsoft Graph API access token"""
        try:
            app = ConfidentialClientApplication(
                client_id=self.client_id,
                client_credential=self.client_secret,
                authority=self.authority
            )
            
            result = app.acquire_token_silent(self.scope, account=None)
            if not result:
                result = app.acquire_token_for_client(scopes=self.scope)
            
            if "access_token" in result:
                return result["access_token"]
            return None
        except Exception as e:
            st.error(f"Error getting access token: {str(e)}")
            return None

    def create_calendar_event(self, user_email: str, attendee_email: str, 
                            subject: str, start_time: datetime, 
                            end_time: datetime, description: str) -> bool:
        """Create a calendar event using Microsoft Graph API"""
        try:
            access_token = self.get_access_token()
            if not access_token:
                return False
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            event_data = {
                "subject": subject,
                "body": {
                    "contentType": "HTML",
                    "content": description
                },
                "start": {
                    "dateTime": start_time.isoformat(),
                    "timeZone": "UTC"
                },
                "end": {
                    "dateTime": end_time.isoformat(),
                    "timeZone": "UTC"
                },
                "attendees": [
                    {
                        "emailAddress": {
                            "address": attendee_email
                        },
                        "type": "required"
                    }
                ]
            }
            
            response = httpx.post(
                f"{self.endpoint}/users/{user_email}/calendar/events",
                headers=headers,
                json=event_data
            )
            
            if response.status_code == 201:
                return True
            st.error(f"Failed to create calendar event: {response.text}")
            return False
            
        except Exception as e:
            st.error(f"Error creating calendar event: {str(e)}")
            return False

