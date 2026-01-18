# firebase_config.py
import firebase_admin
from firebase_admin import credentials, firestore, auth
import streamlit as st
import json

def initialize_firebase():
    """Initialize Firebase with graceful fallback for demo mode"""
    if not firebase_admin._apps:
        try:
            # Check if Firebase secrets exist
            if "firebase" not in st.secrets:
                st.warning("⚠️ Firebase credentials not found. Running in DEMO MODE.")
                st.info("To enable cloud features, add Firebase credentials in Streamlit Cloud secrets.")
                return None, None
            
            # Get Firebase credentials from Streamlit secrets
            firebase_dict = dict(st.secrets["firebase"])
            
            # Initialize Firebase
            cred = credentials.Certificate(firebase_dict)
            firebase_admin.initialize_app(cred)
            
            st.success("✅ Cloud Connected")
            return firestore.client(), auth
            
        except Exception as e:
            st.error(f"❌ Firebase Initialization Failed: {str(e)[:100]}...")
            st.info("Running in DEMO MODE. Data will not be saved to cloud.")
            return None, None
    
    # Already initialized
    return firestore.client(), auth

def get_firestore_client():
    """Get Firestore client or return None for demo mode"""
    try:
        return firestore.client()
    except:
        return None