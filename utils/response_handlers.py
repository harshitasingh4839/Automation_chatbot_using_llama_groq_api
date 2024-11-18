import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
import streamlit as st
from groq import Groq
from .mongo_client import MongoDBClient
from .graph_api import MSGraphAPI
from dataclasses import dataclass
# import logging
# import spacy
# from fuzzywuzzy import fuzz, process

# # Set up logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

@dataclass
class MeetingDetails:
    """Data class to store information required for scheduling meeting using outlook api"""
    client_name: Optional[str] = None
    client_email: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    duration: str = "1 hour"
    purpose: Optional[str] = None
    calendar_event: Optional[str] = None

@dataclass
class PaymentReminderDetails:
    """Data class to store information required for payment reminder"""
    user_email: Optional[str] = None
    client_email: Optional[str] = None
    client_name: Optional[str] = None
    user_name: Optional[str] = None
    designation: Optional[str] = None
    contact_info: Optional[str] = None
    due_date: Optional[str] = None 
    amt_due: Optional[float] = None 
    purpose: Optional[str] = None

def handle_greeting(prompt: str) -> Dict:
    """Handle greetings and general inquiries"""
    greetings = {
        "hello": "Hello! I'm your AI assistant. I can help you with various tasks including meeting scheduling, answering questions, and more. How can I help you today?",
        "hi": "Hi there! How can I assist you today?",
        "hey": "Hey! What can I do for you?",
        "help": "I can help you with:\n1. Scheduling meetings\n2. Answering general questions\n3. Task management\n4. And more!\nWhat would you like to know about?"
    }
    
    prompt_lower = prompt.lower()
    for key in greetings:
        if key in prompt_lower:
            return {
                "response_type": "greeting",
                "message": greetings[key]
            }
    
    return {
        "response_type": "unknown",
        "message": "How can I assist you today?"
    }

def create_extraction_prompt_for_payment_reminder(user_input: str) -> str:
    """
    Creates a structured prompt for the LLM to extract payment reminder information.
    """
    return f"""Extract payment reminder information from the user's request.
Follow these rules strictly:
1. If client_name, amount_due, due_date, or purpose is missing, set them as null.
2. Format due_date as YYYY-MM-DD.
3. Extract amount_due as a numeric value or null.
4. Extract purpose as a clear, concise statement.

Respond ONLY with a JSON object containing these fields:
- client_name: string or null
- amount_due: number or null
- due_date: string (YYYY-MM-DD) or null
- purpose: string or null

User request: {user_input}"""

def create_extraction_prompt_for_meeting_scheduling(user_input: str) -> str:
    """
    Creates a structured prompt for the LLM to extract meeting information.
    """
    return f"""Extract meeting information from the user's request.
Follow these rules strictly:
1. If client_name, date, time, or purpose is missing, set them as null
2. Format date as YYYY-MM-DD
3. Format time as HH:MM in 24-hour format
4. If duration is not specified, do not include it in the response
5. Extract purpose as a clear, concise statement

Respond ONLY with a JSON object containing these fields:
- client_name: string or null
- date: string (YYYY-MM-DD) or null
- time: string (HH:MM) or null
- duration: string or null
- purpose: string or null
 
User request: {user_input}"""

def validate_payment_details(reminder_details: PaymentReminderDetails) -> Optional[str]:
    """
    Validates payment reminder details
    Returns error message if validation fails, None if successful
    """
    if not reminder_details.client_name:
        return "Client name is required."
    
    if reminder_details.amt_due is not None and reminder_details.amt_due <= 0:
        return "Amount due must be greater than 0."
    
    if reminder_details.due_date:
        try:
            datetime.strptime(reminder_details.due_date, '%Y-%m-%d')
        except ValueError:
            return "Invalid date format. Use YYYY-MM-DD."
    
    return None

def extract_payment_info(prompt: str, user_email: str) -> Dict:
    """Handles payment reminder requests and extracts relevent details."""
    mongo_client = MongoDBClient()
    if not mongo_client.connect():
        return{
            "response_type": "error",
            "message": "Database connection failed"
        }
    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))

        completion = client.chat.completions.create(
            model = "llama-3.1-70b-versatile",
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that extracts payment reminder details."
                },
                {"role": "user","content":create_extraction_prompt_for_payment_reminder(prompt)}

            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )

        extracted_info = json.loads(completion.choices[0].message.content)

        reminder_details = PaymentReminderDetails(
            user_email=user_email,
            client_name=extracted_info.get("client_name"),
            amt_due=extracted_info.get("amount_due"),
            due_date=extracted_info.get("due_date"),
            purpose=extracted_info.get("purpose")
        )
        # Handle missing client_name and others
        validation_error = validate_payment_details(reminder_details)
        if validation_error:
            return {
                "response_type": "error",
                "message": validation_error,

            }
        client_exists, reminder_details.client_email = mongo_client.verify_client(reminder_details.client_name)
        if not client_exists:
            return {
                "response_type": "error",
                "message": f"Client '{reminder_details.client_name}' not found."
            }

        # Send email or notification for payment reminder
        response_message = f"Payment reminder for {reminder_details.client_name}: Due amount: {reminder_details.amt_due}. Due date: {reminder_details.due_date}."
        return {
            "response_type": "payment_reminder",
            "message": response_message
        }
    except Exception as e:
        return {
            "response_type": "error",
            "message": f"An error occurred: {str(e)}"
        }
        
    finally:
        mongo_client.close()
  
def parse_duration(duration_str: str) -> int:
    """
    Parses duration string and returns minutes.
    """
    if not duration_str:
        return 60  # Default 1 hour
    
    duration_str = duration_str.lower()
    try:
        if 'hour' in duration_str:
            return int(duration_str.split()[0]) * 60
        elif 'min' in duration_str:
            return int(duration_str.split()[0])
        else:
            return 60  # Default if format is unrecognized
    except (ValueError, IndexError):
        return 60

def validate_date_time(date_str: Optional[str], time_str: Optional[str]) -> tuple[bool, str]:
    """
    Validates date and time formats.
    Returns (is_valid: bool, error_message: str)
    """
    if date_str:
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return False, f"Invalid date format: {date_str}. Please use YYYY-MM-DD format."

    if time_str:
        try:
            datetime.strptime(time_str, "%H:%M")
        except ValueError:
            return False, f"Invalid time format: {time_str}. Please use HH:MM format (24-hour)."

    return True, ""

def create_calendar_event(details: MeetingDetails, user_email: str, graph_api: MSGraphAPI) -> Tuple[bool, str]:
    """
    Creates a calendar event using the Microsoft Graph API.
    Returns (success: bool, message: str)
    """
    try:
        start_time = datetime.strptime(f"{details.date} {details.time}", "%Y-%m-%d %H:%M")
        duration_mins = parse_duration(details.duration)
        end_time = start_time + timedelta(minutes=duration_mins)

        event_created = graph_api.create_calendar_event(
            user_email=user_email,
            attendee_email=details.client_email,
            subject=f"Meeting with {details.client_name}",
            start_time=start_time,
            end_time=end_time,
            description=details.purpose or 'Business Meeting'
        )

        if event_created:
            return True, "created"
        return False, "failed"

    except Exception as e:
        return False, f"error: {str(e)}"

def get_missing_parameters(details: MeetingDetails) -> List[str]:
    """
    Returns a list of missing required parameters.
    """
    missing = []
    if not details.client_name:
        missing.append("client name")
    if not details.date:
        missing.append("date")
    if not details.time:
        missing.append("time")
    if not details.purpose:
        missing.append("purpose")
    return missing

def format_meeting_response(details: MeetingDetails, missing_params: List[str]) -> str:
    """Formats a user-friendly response based on the extracted details and missing parameters."""
    if missing_params:
        missing_str = ', '.join(missing_params)
        return f"I need the following information to schedule the meeting: {missing_str}."

    response = f"Meeting scheduled with {details.client_name} on {details.date} at {details.time} for {details.duration}."
    
    if details.purpose:
        response += f" Purpose: {details.purpose}."

    return response

# def format_meeting_response(details: MeetingDetails, missing_params: List[str]) -> str:
#     """
#     Formats a user-friendly response based on the extracted details and missing parameters.
#     """
#     if missing_params:
#         if len(missing_params) == 1:
#             return f"I need the {missing_params[0]} to schedule the meeting. Could you please provide it?"
#         else:
#             missing_str = ", ".join(missing_params[:-1]) + f" and {missing_params[-1]}"
#             return f"I need the {missing_str} to schedule the meeting. Could you please provide them?"

#     response = f"Meeting scheduled with {details.client_name} on {details.date} at {details.time}"
#     response += f" for {details.duration}"

#     if details.purpose:
#         response += f". Purpose: {details.purpose}"

#     if details.calendar_event == "created":
#         response += ". Calendar event has been created and invitations sent."
#     elif details.calendar_event == "failed":
#         response += ". Note: Failed to create calendar event."
#     elif details.calendar_event and details.calendar_event.startswith("error"):
#         response += f". Note: Calendar event creation failed: {details.calendar_event}"

#     return response





# def extract_client_name(prompt: str, mongo_client) -> Tuple[str, float]:
#     """
#     Extract client name using SpaCy NER and FuzzyWuzzy matching against database records.
#     Returns tuple of (best_match_name, confidence_score)
#     """
#     # Load SpaCy model
#     nlp = spacy.load("en_core_web_sm")
    
#     # Process the prompt
#     doc = nlp(prompt)
    
#     # Extract potential client names (PERSON and ORG entities)
#     potential_names = []
#     for ent in doc.ents:
#         if ent.label_ in ["PERSON"]:
#             potential_names.append(ent.text)
    
#     if not potential_names:
#         return None, 0.0
    
#     # Get list of existing client names from database
#     existing_clients = mongo_client.get_all_client_names()
    
#     # Find best match for each potential name
#     best_matches = []
#     for name in potential_names:
#         # Use process.extractOne to find the best match
#         match = process.extractOne(
#             name,
#             existing_clients,
#             scorer=fuzz.token_sort_ratio,
#             score_cutoff=70  # Minimum similarity score threshold
#         )
#         if match:
#             best_matches.append(match)  # (matched_name, score)
    
#     # Return the highest scoring match if any found
#     if best_matches:
#         best_match = max(best_matches, key=lambda x: x[1])
#         return best_match
    
#     return None, 0.0

def extract_meeting_info(prompt: str, user_email: str) -> Dict:
    """Extract and process meeting information"""
    mongo_client = MongoDBClient()
    if not mongo_client.connect():
        return {
            "response_type": "error",
            "message": "Database connection failed"
        }

    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        graph_api = MSGraphAPI()

        # # Extract client name using NER and fuzzy matching
        # client_name, confidence_score = extract_client_name(prompt, mongo_client)

        # Get initial extraction from LLM
        completion = client.chat.completions.create(
            # model="llama3-groq-70b-8192-tool-use-preview",
            model = "llama-3.1-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that extracts meeting details and returns them in JSON format."
                },
                {"role": "user", "content": create_extraction_prompt_for_meeting_scheduling(prompt)}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )

        # Parse the response
        extracted_info = json.loads(completion.choices[0].message.content)
        
        # # Override LLM's client name if NER found a high-confidence match
        # if client_name and confidence_score >= 60:
        #     extracted_info["client_name"] = client_name
        
        # Create MeetingDetails object with extracted info
        details = MeetingDetails(
            client_name=extracted_info.get("client_name"),
            date=extracted_info.get("date"),
            time=extracted_info.get("time"),
            duration=extracted_info.get("duration", "1 hour"),
            purpose=extracted_info.get("purpose")
        )

        # Validate date and time formats
        is_valid, error_message = validate_date_time(details.date, details.time)
        if not is_valid:
            return {
                "response_type": "error",
                "message": error_message
            }

        # Verify client and get email if client name is provided
        if details.client_name:
            client_exists, client_email = mongo_client.verify_client(details.client_name)
            if not client_exists:
                return {
                    "response_type": "error",
                    "message": f"Client '{details.client_name}' not found"
                }
            details.client_email = client_email

            # Create calendar event if all required fields are present
            if all([details.date, details.time]):
                success, status = create_calendar_event(details, user_email, graph_api)
                # details.calendar_event = status

        # Get missing parameters
        missing_params = get_missing_parameters(details)
        
        # Generate response
        response = {
            "response_type": "meeting",
            "details": {
                "client_name": details.client_name,
                "client_email": details.client_email,
                "date": details.date,
                "time": details.time,
                "duration": details.duration,
                "purpose": details.purpose,
                # "calendar_event": details.calendar_event,
                # "name_confidence": confidence_score if client_name else 0
            },
            "missing_params": missing_params,
            "message": format_meeting_response(details, missing_params)

        }

        return response

    except Exception as e:
        return {
            "response_type": "error",
            "message": f"Error processing meeting request: {str(e)}"
        }
    finally:
        mongo_client.close()

def handle_general_query(prompt: str) -> Dict:
    """Handle general questions and queries"""
    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        completion = client.chat.completions.create(
            model="llama3-groq-70b-8192-tool-use-preview",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Provide clear and concise answers."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        
        return {
            "response_type": "general",
            "message": completion.choices[0].message.content
        }
    except Exception as e:
        return {
            "response_type": "error",
            "message": f"Error processing query: {str(e)}"
        }

def format_response(response_data: Dict) -> str:
    """Format the response based on response type"""
    if response_data["response_type"] == "error":
        return f"Sorry, an error occurred: {response_data['message']}"
    
    elif response_data["response_type"] == "greeting":
        return response_data["message"]
    
    elif response_data["response_type"] == "meeting":
        details = response_data["details"]
        if "error" in details:
            return f"Sorry, {details['error']}"
        
        missing = []
        if not details.get("client_name"): missing.append("client name")
        if not details.get("date"): missing.append("date")
        if not details.get("time"): missing.append("time")
        
        if missing:
            return f"I need the following information to schedule the meeting: {', '.join(missing)}"
        
        response = f"Meeting scheduled with {details['client_name']}"
        if details.get("client_email"):
            response += f" (email: {details['client_email']})"
        response += f" on {details['date']} at {details['time']}"
        if details.get("duration"): 
            response += f" for {details['duration']}"
        if details.get("purpose"): 
            response += f". Purpose: {details['purpose']}"
        
        # Add calendar event status
        if details.get("calendar_event") == "created":
            response += "\nOutlook calendar event has been created and invites have been sent."
        elif details.get("calendar_event") == "failed":
            response += "\nNote: Failed to create Outlook calendar event."
        elif details.get("calendar_event", "").startswith("error"):
            response += f"\nNote: Error creating calendar event - {details['calendar_event']}"
        
        return response
    
    elif response_data["response_type"] == "payment_reminder":
        return response_data["message"]
    
    elif response_data["response_type"] == "general":
        return response_data["message"]
    
    return "I'm not sure how to handle that request."

def determine_intent(prompt: str) -> str:
    """Determine the intent of the user's prompt"""
    prompt_lower = prompt.lower()
    
    # Check for greetings
    if any(word in prompt_lower for word in ["hello", "hi", "hey", "help"]):
        return "greeting"
    
    # Check for meeting-related keywords
    if any(word in prompt_lower for word in ["schedule", "meeting", "appointment","arrange", "book"]):
        return "meeting"
    
    # Check for payment reminder keywords
    if any(word in prompt_lower for word in ["payment", "reminder", "due", "amount", "pay", "invoice"]):
        return "payment_reminder"
    
    # Default to general query
    return "general"