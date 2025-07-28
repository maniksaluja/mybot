from typing import Dict, List, Any
import time
from datetime import datetime, timedelta
from config import FIND_SEARCH_TIMEOUT
# Store user search sessions
# Format: {user_id: {"results": [], "query": str, "page": int, "timestamp": float}}
user_search_sessions: Dict[int, Dict[str, Any]] = {}

# Constants
RESULTS_PER_PAGE = 10


def store_search_results(user_id: int, results: List[Dict], query: str) -> None:
    """Store search results for a user session"""
    user_search_sessions[user_id] = {
        "results": results,
        "query": query,
        "page": 0,  # Start with first page (index 0)
        "timestamp": time.time(),
        "total_pages": (len(results) + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE  # Calculate total pages
    }

def get_paginated_results(user_id: int, page: int = None) -> Dict[str, Any]:
    """Get paginated results for a user
    
    Returns dict with:
    - results: list of results for current page
    - current_page: current page number (1-based)
    - total_pages: total number of pages
    - has_next: whether there's a next page
    - has_prev: whether there's a previous page
    - query: original search query
    """
    if user_id not in user_search_sessions:
        return None
    
    session = user_search_sessions[user_id]
    
    # Update page if provided
    if page is not None:
        session["page"] = page
    
    current_page = session["page"]
    total_results = len(session["results"])
    total_pages = session["total_pages"]
    
    # Calculate start and end indices for current page
    start_idx = current_page * RESULTS_PER_PAGE
    end_idx = min(start_idx + RESULTS_PER_PAGE, total_results)
    
    # Get results for current page
    page_results = session["results"][start_idx:end_idx]
    
    return {
        "results": page_results,
        "current_page": current_page + 1,  # Convert to 1-based for display
        "total_pages": total_pages,
        "has_next": current_page < total_pages - 1,
        "has_prev": current_page > 0,
        "query": session["query"],
        "total_results": total_results
    }

def update_page(user_id: int, direction: str) -> Dict[str, Any]:
    """Update page for a user (next/prev) and return paginated results"""
    if user_id not in user_search_sessions:
        return None
    
    session = user_search_sessions[user_id]
    current_page = session["page"]
    total_pages = session["total_pages"]
    
    if direction == "next" and current_page < total_pages - 1:
        session["page"] += 1
    elif direction == "prev" and current_page > 0:
        session["page"] -= 1
    
    # Update session timestamp
    session["timestamp"] = time.time()
    
    return get_paginated_results(user_id)

def clean_expired_sessions():
    """Remove expired search sessions"""
    current_time = time.time()
    expired_users = [
        user_id for user_id, session in user_search_sessions.items()
        if current_time - session["timestamp"] > FIND_SEARCH_TIMEOUT
    ]
    
    for user_id in expired_users:
        user_search_sessions.pop(user_id, None)

def has_active_session(user_id: int) -> bool:
    """Check if user has an active search session"""
    if user_id not in user_search_sessions:
        return False
    
    # Check if session is expired
    current_time = time.time()
    if current_time - user_search_sessions[user_id]["timestamp"] > FIND_SEARCH_TIMEOUT:
        user_search_sessions.pop(user_id, None)
        return False
    
    return True
