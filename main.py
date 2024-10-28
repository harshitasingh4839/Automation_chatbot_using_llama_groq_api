import streamlit as st
from dotenv import load_dotenv
from utils.response_handlers import (
    determine_intent, handle_greeting, extract_meeting_info,
    handle_task_management, handle_general_query, format_response
)

# Load environment variables
load_dotenv()

def bot_calling_functions(user_prompt: str, user_email: str) -> str:
    """Main function for handling user input using function calling"""
    try:
        # Determine intent
        intent = determine_intent(user_prompt)
        
        # Call appropriate function based on intent
        if intent == "greeting":
            response_data = handle_greeting(user_prompt)
        elif intent == "meeting":
            response_data = extract_meeting_info(user_prompt, user_email)
        elif intent == "task":
            response_data = handle_task_management(user_prompt)
        else:
            response_data = handle_general_query(user_prompt)
        
        # Format and return response
        return format_response(response_data)
    
    except Exception as e:
        return f"I encountered an error: {str(e)}"

def main():
    st.set_page_config(page_title="AI Assistant", page_icon="🤖")
    st.title("AI Assistant 🤖")
    
    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "user_email" not in st.session_state:
        st.session_state.user_email = ""
    
    # Email input section
    if not st.session_state.user_email:
        st.write("Please enter your email address to continue:")
        email_input = st.text_input("Your Email:")
        if st.button("Submit Email"):
            if email_input and "@" in email_input:
                st.session_state.user_email = email_input
                st.rerun()
            else:
                st.error("Please enter a valid email address.")
        return
    
    # Display current user email
    st.sidebar.write(f"Current user: {st.session_state.user_email}")
    if st.sidebar.button("Change Email"):
        st.session_state.user_email = ""
        st.rerun()
    
    # Chat interface
    for message in st.session_state.messages:
        role = "You" if message["role"] == "user" else "Bot"
        st.markdown(f"**{role}:** {message['content']}")
    
    # User input
    user_input = st.text_input("Type your message:")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("Send", use_container_width=True):
            if user_input:
                # Add user message to chat
                st.session_state.messages.append({"role": "user", "content": user_input})
                
                # Process message and get response
                response = bot_calling_functions(user_input, st.session_state.user_email)
                
                # Add bot response to chat
                st.session_state.messages.append({"role": "assistant", "content": response})
                st.rerun()
    
    with col2:
        if st.button("Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

if __name__ == "__main__":
    main()