"""
API Client for SAIV Backend
"""
import requests
from typing import Dict, Any, Tuple, Optional
import os

class APIClient:
    """Client for interacting with SAIV backend API"""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.getenv("BACKEND_URL", "http://localhost:8000/api/v1")
        if not self.base_url.endswith("/api/v1"):
            self.base_url = self.base_url.rstrip("/") + "/api/v1"
        self.token = None
        self.session = requests.Session()

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _handle_response(self, response: requests.Response) -> Tuple[bool, Any]:
        try:
            if response.status_code in [200, 201]:
                return True, response.json()
            elif response.status_code == 204:
                return True, {}
            else:
                try:
                    error_data = response.json()
                    return False, error_data.get('detail', f"Error {response.status_code}")
                except:
                    return False, f"Error {response.status_code}"
        except Exception as e:
            return False, str(e)

    def login(self, email: str, password: str) -> Tuple[bool, Any]:
        try:
            response = self.session.post(
                f"{self.base_url}/auth/login",
                json={"email": email, "password": password},
                headers={"Content-Type": "application/json"}
            )
            success, result = self._handle_response(response)
            if success:
                self.token = result.get('access_token')
            return success, result
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    # Statistics
    def get_overview_statistics(self, days: int = 7) -> Tuple[bool, Any]:
        try:
            response = self.session.get(
                f"{self.base_url}/stats/overview?days={days}",
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, str(e)

    def get_course_statistics(self, course_id: str) -> Tuple[bool, Any]:
        try:
            response = self.session.get(
                f"{self.base_url}/stats/courses/{course_id}",
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, str(e)

    def get_session_statistics(self, session_id: str) -> Tuple[bool, Any]:
        try:
            response = self.session.get(
                f"{self.base_url}/stats/sessions/{session_id}",
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, str(e)

    # Courses
    def get_courses(self) -> Tuple[bool, Any]:
        try:
            response = self.session.get(
                f"{self.base_url}/courses/",
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, str(e)

    def create_course(self, data: Dict[str, Any]) -> Tuple[bool, Any]:
        try:
            response = self.session.post(
                f"{self.base_url}/courses/",
                json=data,
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, str(e)

    def update_course(self, course_id: str, data: Dict[str, Any]) -> Tuple[bool, Any]:
        try:
            response = self.session.put(
                f"{self.base_url}/courses/{course_id}",
                json=data,
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, str(e)

    def delete_course(self, course_id: str) -> Tuple[bool, Any]:
        try:
            response = self.session.delete(
                f"{self.base_url}/courses/{course_id}",
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, str(e)

    # Sessions
    def get_sessions(self, course_id: Optional[str] = None) -> Tuple[bool, Any]:
        try:
            url = f"{self.base_url}/sessions/"
            if course_id:
                url += f"?course_id={course_id}"
            response = self.session.get(url, headers=self._get_headers())
            return self._handle_response(response)
        except Exception as e:
            return False, str(e)

    def create_session(self, data: Dict[str, Any]) -> Tuple[bool, Any]:
        try:
            response = self.session.post(
                f"{self.base_url}/sessions/",
                json=data,
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, str(e)

    def update_session(self, session_id: str, data: Dict[str, Any]) -> Tuple[bool, Any]:
        try:
            response = self.session.patch(
                f"{self.base_url}/sessions/{session_id}",
                json=data,
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, str(e)

    def update_session_status(self, session_id: str, status: str) -> Tuple[bool, Any]:
        try:
            response = self.session.patch(
                f"{self.base_url}/admin/sessions/{session_id}/status",
                json={"status": status},
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, str(e)

    def delete_session(self, session_id: str) -> Tuple[bool, Any]:
        try:
            response = self.session.delete(
                f"{self.base_url}/sessions/{session_id}",
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, str(e)

    # Check-ins
    def get_session_checkins(self, session_id: str) -> Tuple[bool, Any]:
        try:
            response = self.session.get(
                f"{self.base_url}/checkins/session/{session_id}",
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, str(e)

    def get_flagged_checkins(self, limit: int = 50) -> Tuple[bool, Any]:
        try:
            response = self.session.get(
                f"{self.base_url}/checkins/flagged?limit={limit}",
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, str(e)

    def review_checkin(self, checkin_id: str, status: str, review_notes: str = "") -> Tuple[bool, Any]:
        try:
            response = self.session.post(
                f"{self.base_url}/checkins/{checkin_id}/review",
                json={"status": status, "review_notes": review_notes},
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, str(e)

    # Enrollments
    def get_course_enrollments(self, course_id: str) -> Tuple[bool, Any]:
        try:
            response = self.session.get(
                f"{self.base_url}/enrollments/course/{course_id}",
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, str(e)

    def create_enrollment(self, student_id: str, course_id: str) -> Tuple[bool, Any]:
        try:
            response = self.session.post(
                f"{self.base_url}/admin/enrollments/",
                json={"student_id": student_id, "course_id": course_id},
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, str(e)

    def bulk_enroll(self, course_id: str, student_emails: list, create_accounts: bool = False) -> Tuple[bool, Any]:
        try:
            response = self.session.post(
                f"{self.base_url}/enrollments/bulk",
                json={
                    "course_id": course_id,
                    "student_emails": student_emails,
                    "create_accounts": create_accounts
                },
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, str(e)

    # Users
    def get_users(self, role: str = None) -> Tuple[bool, Any]:
        try:
            url = f"{self.base_url}/users/"
            if role:
                url += f"?role={role}"
            response = self.session.get(url, headers=self._get_headers())
            return self._handle_response(response)
        except Exception as e:
            return False, str(e)

    # Export
    def export_course_attendance(self, course_id: str, format: str = "csv"):
        try:
            response = self.session.get(
                f"{self.base_url}/export/attendance/{course_id}?format={format}",
                headers=self._get_headers()
            )
            if response.status_code == 200:
                return True, response.content
            return self._handle_response(response)
        except Exception as e:
            return False, str(e)

    def export_session_data(self, session_id: str, format: str = "csv"):
        try:
            response = self.session.get(
                f"{self.base_url}/export/session/{session_id}?format={format}",
                headers=self._get_headers()
            )
            if response.status_code == 200:
                return True, response.content
            return self._handle_response(response)
        except Exception as e:
            return False, str(e)

    # Audit
    def get_audit_logs(self, **params) -> Tuple[bool, Any]:
        try:
            response = self.session.get(
                f"{self.base_url}/audit/",
                params=params,
                headers=self._get_headers()
            )
            return self._handle_response(response)
        except Exception as e:
            return False, str(e)
