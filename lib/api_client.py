"""
API Client for SAIV Backend
Handles all communication with the backend API
"""

import os
import requests
from typing import Dict, Any, Tuple, Optional, List
import streamlit as st

# Get backend URL from environment variable, default to localhost for local development
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

class APIClient:
    """Client for interacting with SAIV backend API"""

    def __init__(self, base_url: str = None):
        """
        Initialize API client

        Args:
            base_url: Base URL for the API
        """
        self.base_url = base_url or f"{BACKEND_URL}/api/v1"
        self.token = None
        self.session = requests.Session()

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _handle_response(self, response: requests.Response) -> Tuple[bool, Any]:
        """
        Handle API response

        Args:
            response: Response object from requests

        Returns:
            Tuple of (success, data/error_message)
        """
        try:
            if response.status_code == 200 or response.status_code == 201:
                return True, response.json()
            elif response.status_code == 401:
                return False, "Authentication failed. Please login again."
            elif response.status_code == 403:
                return False, "Access denied. Insufficient permissions."
            elif response.status_code == 404:
                return False, "Resource not found."
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('detail', f"Error {response.status_code}")
                except:
                    error_msg = f"Error {response.status_code}: {response.text}"
                return False, error_msg
        except Exception as e:
            return False, f"Request failed: {str(e)}"

    def login(self, email: str, password: str) -> Tuple[bool, Any]:
        """
        Login to the system

        Args:
            email: User email
            password: User password

        Returns:
            Tuple of (success, response_data/error_message)
        """
        try:
            data = {
                "email": email,
                "password": password
            }
            response = self.session.post(
                f"{self.base_url}/auth/login",
                json=data,
                headers=self._get_headers()
            )
            success, result = self._handle_response(response)
            if success:
                self.token = result.get('access_token')
            return success, result
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    # Statistics endpoints
    def get_overview_statistics(self, days: int = 7) -> Tuple[bool, Any]:
        """Get overview statistics"""
        try:
            response = self.session.get(
                f"{self.base_url}/stats/overview?days={days}",
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    def get_course_statistics(self, course_id: str) -> Tuple[bool, Any]:
        """Get statistics for a specific course"""
        try:
            response = self.session.get(
                f"{self.base_url}/stats/courses/{course_id}",
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    def get_session_statistics(self, session_id: str) -> Tuple[bool, Any]:
        """Get statistics for a specific session"""
        try:
            response = self.session.get(
                f"{self.base_url}/stats/sessions/{session_id}",
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    def get_student_statistics(self, student_id: str) -> Tuple[bool, Any]:
        """Get statistics for a specific student"""
        try:
            response = self.session.get(
                f"{self.base_url}/stats/students/{student_id}",
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    # Course endpoints
    def get_courses(self) -> Tuple[bool, Any]:
        """Get list of all courses"""
        try:
            response = self.session.get(
                f"{self.base_url}/courses/",
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    def get_course(self, course_id: int) -> Tuple[bool, Any]:
        """Get course details"""
        try:
            response = self.session.get(
                f"{self.base_url}/courses/{course_id}",
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    def get_course_enrollments(self, course_id: int) -> Tuple[bool, Any]:
        """Get enrollments for a course"""
        try:
            response = self.session.get(
                f"{self.base_url}/courses/{course_id}/enrollments",
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    # Session endpoints
    def get_sessions(self, course_id: Optional[int] = None) -> Tuple[bool, Any]:
        """Get list of sessions"""
        try:
            url = f"{self.base_url}/sessions/"
            if course_id:
                url += f"?course_id={course_id}"
            response = self.session.get(url, headers=self._get_headers())
            return self._handle_response(response)
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    def get_session(self, session_id: int) -> Tuple[bool, Any]:
        """Get session details"""
        try:
            response = self.session.get(
                f"{self.base_url}/sessions/{session_id}",
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    def get_session_checkins(self, session_id: str) -> Tuple[bool, Any]:
        """Get check-ins for a session"""
        try:
            response = self.session.get(
                f"{self.base_url}/checkins/session/{session_id}",
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    def get_active_sessions(self) -> Tuple[bool, Any]:
        """Get currently active sessions"""
        try:
            response = self.session.get(
                f"{self.base_url}/sessions/active",
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    # Check-in endpoints
    def get_flagged_checkins(self, limit: int = 50) -> Tuple[bool, Any]:
        """Get flagged check-ins requiring review"""
        try:
            response = self.session.get(
                f"{self.base_url}/checkins/flagged?limit={limit}",
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    def get_recent_checkins(self, limit: int = 20) -> Tuple[bool, Any]:
        """Get recent check-ins"""
        try:
            response = self.session.get(
                f"{self.base_url}/checkins/recent?limit={limit}",
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    def update_checkin_status(self, checkin_id: int, status: str, notes: Optional[str] = None) -> Tuple[bool, Any]:
        """Update check-in status"""
        try:
            data = {"status": status}
            if notes:
                data["notes"] = notes
            response = self.session.patch(
                f"{self.base_url}/checkins/{checkin_id}/status",
                json=data,
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    # User endpoints
    def get_students(self, course_id: Optional[int] = None) -> Tuple[bool, Any]:
        """Get list of students"""
        try:
            url = f"{self.base_url}/users/?role=student"
            if course_id:
                url += f"&course_id={course_id}"
            response = self.session.get(url, headers=self._get_headers())
            return self._handle_response(response)
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    def get_user(self, user_id: int) -> Tuple[bool, Any]:
        """Get user details"""
        try:
            response = self.session.get(
                f"{self.base_url}/users/{user_id}",
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    # Audit log endpoints
    def get_audit_logs(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        success: Optional[bool] = None,
        offset: int = 0,
        limit: int = 100
    ) -> Tuple[bool, Any]:
        """Get audit logs with filters"""
        try:
            params = {
                "offset": offset,
                "limit": limit
            }
            if user_id:
                params["user_id"] = user_id
            if action:
                params["action"] = action
            if resource_type:
                params["resource_type"] = resource_type
            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date
            if success is not None:
                params["success"] = success

            response = self.session.get(
                f"{self.base_url}/audit/",
                params=params,
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    # Review check-in
    def review_checkin(self, checkin_id: str, status: str, review_notes: str = "") -> Tuple[bool, Any]:
        """Review a flagged or appealed check-in"""
        try:
            response = self.session.post(
                f"{self.base_url}/checkins/{checkin_id}/review",
                json={"status": status, "review_notes": review_notes},
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    # Export endpoints
    def export_course_attendance(self, course_id: str, format: str = "csv") -> Tuple[bool, Any]:
        """Export course attendance data"""
        try:
            response = self.session.get(
                f"{self.base_url}/export/attendance/{course_id}?format={format}",
                headers=self._get_headers()
            )
            if response.status_code == 200:
                return True, response.content
            else:
                return self._handle_response(response)
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    def export_session_data(self, session_id: str, format: str = "csv") -> Tuple[bool, Any]:
        """Export session data"""
        try:
            response = self.session.get(
                f"{self.base_url}/export/session/{session_id}?format={format}",
                headers=self._get_headers()
            )
            if response.status_code == 200:
                return True, response.content
            else:
                return self._handle_response(response)
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    # Enrollment endpoints
    def get_course_enrollments(self, course_id: str) -> Tuple[bool, Any]:
        """Get enrollments for a course"""
        try:
            response = self.session.get(
                f"{self.base_url}/enrollments/course/{course_id}",
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, f"Connection error: {str(e)}"
