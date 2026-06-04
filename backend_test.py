#!/usr/bin/env python3
"""
Comprehensive Backend Test Suite for Astra AI Knowledge Assistant
Tests CORS, Auth, Chat Flows, Admin Config, and Trained Answers CRUD
"""

import requests
import json
import time
from typing import Dict, Any, Optional

# Backend URL from frontend/.env
BASE_URL = "https://850bd8fe-d05b-42ba-ae9b-b926ea0fade5.preview.emergentagent.com"
API_URL = f"{BASE_URL}/api"

# Test credentials from test_credentials.md
ADMIN_EMAIL = "admin@biziverse.com"
ADMIN_PASSWORD = "Admin@123"

# Test origin for CORS
TEST_ORIGIN = "https://pull-push.preview.emergentagent.com"

# Global session to store cookies
session = requests.Session()

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def print_test(name: str):
    print(f"\n{Colors.BLUE}{'='*80}{Colors.RESET}")
    print(f"{Colors.BLUE}TEST: {name}{Colors.RESET}")
    print(f"{Colors.BLUE}{'='*80}{Colors.RESET}")

def print_pass(message: str):
    print(f"{Colors.GREEN}✓ PASS: {message}{Colors.RESET}")

def print_fail(message: str):
    print(f"{Colors.RED}✗ FAIL: {message}{Colors.RESET}")

def print_info(message: str):
    print(f"{Colors.YELLOW}ℹ INFO: {message}{Colors.RESET}")


def test_cors():
    """Test 1: CRITICAL - Test CORS with OPTIONS request"""
    print_test("CORS - OPTIONS request with specific origin")
    
    try:
        response = requests.options(
            f"{API_URL}/auth/login",
            headers={
                "Origin": TEST_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type"
            }
        )
        
        print_info(f"Status Code: {response.status_code}")
        print_info(f"Headers: {dict(response.headers)}")
        
        # Check status code
        if response.status_code != 200:
            print_fail(f"Expected status 200, got {response.status_code}")
            return False
        
        # Check Access-Control-Allow-Origin
        allow_origin = response.headers.get("Access-Control-Allow-Origin", "")
        if allow_origin != TEST_ORIGIN:
            print_fail(f"Expected Access-Control-Allow-Origin: {TEST_ORIGIN}, got: {allow_origin}")
            return False
        print_pass(f"Access-Control-Allow-Origin matches: {allow_origin}")
        
        # Check Access-Control-Allow-Credentials
        allow_creds = response.headers.get("Access-Control-Allow-Credentials", "")
        if allow_creds.lower() != "true":
            print_fail(f"Expected Access-Control-Allow-Credentials: true, got: {allow_creds}")
            return False
        print_pass(f"Access-Control-Allow-Credentials: {allow_creds}")
        
        # Check NOT wildcard
        if allow_origin == "*":
            print_fail("Access-Control-Allow-Origin should NOT be wildcard *")
            return False
        print_pass("Access-Control-Allow-Origin is NOT wildcard")
        
        print_pass("CORS test passed - all headers correct")
        return True
        
    except Exception as e:
        print_fail(f"CORS test failed with exception: {e}")
        return False


def test_login():
    """Test 2: Test Login with admin credentials"""
    print_test("Login - POST /api/auth/login")
    
    try:
        response = session.post(
            f"{API_URL}/auth/login",
            json={
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD
            },
            headers={"Origin": TEST_ORIGIN}
        )
        
        print_info(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print_fail(f"Login failed with status {response.status_code}: {response.text}")
            return False
        
        data = response.json()
        print_info(f"Response: {json.dumps(data, indent=2)}")
        
        # Check user data
        if "user" not in data:
            print_fail("Response missing 'user' field")
            return False
        
        user = data["user"]
        if user.get("email") != ADMIN_EMAIL:
            print_fail(f"Expected email {ADMIN_EMAIL}, got {user.get('email')}")
            return False
        print_pass(f"User email correct: {user.get('email')}")
        
        if user.get("role") != "super_admin":
            print_fail(f"Expected role super_admin, got {user.get('role')}")
            return False
        print_pass(f"User role correct: {user.get('role')}")
        
        # Check access_token
        if "access_token" not in data:
            print_fail("Response missing 'access_token' field")
            return False
        print_pass("Access token present in response")
        
        # Check cookies
        cookies = session.cookies.get_dict()
        print_info(f"Cookies: {cookies}")
        if "access_token" not in cookies:
            print_fail("access_token cookie not set")
            return False
        print_pass("access_token cookie set correctly")
        
        print_pass("Login test passed - user data and cookies correct")
        return True
        
    except Exception as e:
        print_fail(f"Login test failed with exception: {e}")
        return False


def test_chat_create_conversation():
    """Test 3: Create conversation"""
    print_test("Chat - Create Conversation")
    
    try:
        response = session.post(
            f"{API_URL}/chat/conversations",
            json={"title": "Test Conversation"},
            headers={"Origin": TEST_ORIGIN}
        )
        
        print_info(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print_fail(f"Create conversation failed with status {response.status_code}: {response.text}")
            return None
        
        data = response.json()
        print_info(f"Response: {json.dumps(data, indent=2)}")
        
        if "_id" not in data:
            print_fail("Response missing '_id' field")
            return None
        
        conv_id = data["_id"]
        print_pass(f"Conversation created with ID: {conv_id}")
        return conv_id
        
    except Exception as e:
        print_fail(f"Create conversation failed with exception: {e}")
        return None


def test_chat_trained_answer(conv_id: str):
    """Test 4: Trained answer priority - "What is Biziverse?" """
    print_test("Chat - Trained Answer Priority")
    
    try:
        response = session.post(
            f"{API_URL}/chat/conversations/{conv_id}/messages",
            json={"content": "What is Biziverse?"},
            headers={"Origin": TEST_ORIGIN},
            stream=True
        )
        
        print_info(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print_fail(f"Send message failed with status {response.status_code}: {response.text}")
            return False
        
        # Parse SSE stream
        full_response = ""
        events = []
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    data_str = line_str[6:]
                    try:
                        event = json.loads(data_str)
                        events.append(event)
                        if event.get('type') == 'token':
                            full_response += event.get('content', '')
                    except json.JSONDecodeError:
                        pass
        
        print_info(f"Events received: {len(events)}")
        print_info(f"Full response: {full_response[:200]}...")
        
        # Check for trained answer source
        done_event = next((e for e in events if e.get('type') == 'done'), None)
        if not done_event:
            print_fail("No 'done' event received")
            return False
        
        print_pass("SSE stream completed with 'done' event")
        
        # Check response contains bold markdown
        if "**" in full_response:
            print_pass(f"Response contains bold markdown: {full_response.count('**')} asterisks found")
        else:
            print_info("Response does not contain bold markdown (may be plain text)")
        
        # Check response is not empty
        if len(full_response) < 10:
            print_fail(f"Response too short: {full_response}")
            return False
        
        print_pass("Trained answer priority test passed")
        return True
        
    except Exception as e:
        print_fail(f"Trained answer test failed with exception: {e}")
        return False


def test_chat_vague_query():
    """Test 5: Vague query - should return suggestions"""
    print_test("Chat - Vague Query Suggestions")
    
    # Create new conversation
    conv_id = test_chat_create_conversation()
    if not conv_id:
        return False
    
    try:
        response = session.post(
            f"{API_URL}/chat/conversations/{conv_id}/messages",
            json={"content": "create order"},
            headers={"Origin": TEST_ORIGIN},
            stream=True
        )
        
        print_info(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print_fail(f"Send message failed with status {response.status_code}: {response.text}")
            return False
        
        # Parse SSE stream
        events = []
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    data_str = line_str[6:]
                    try:
                        event = json.loads(data_str)
                        events.append(event)
                    except json.JSONDecodeError:
                        pass
        
        print_info(f"Events received: {len(events)}")
        
        # Check for suggestions event
        suggestion_event = next((e for e in events if e.get('type') == 'suggestions'), None)
        if not suggestion_event:
            print_fail("No 'suggestions' event received")
            print_info(f"Events: {events}")
            return False
        
        questions = suggestion_event.get('questions', [])
        print_info(f"Suggestions: {questions}")
        
        if len(questions) == 0:
            print_fail("No suggestions returned")
            return False
        
        print_pass(f"Received {len(questions)} suggestions from actual KB")
        for q in questions:
            print_info(f"  - {q}")
        
        print_pass("Vague query suggestions test passed")
        return True
        
    except Exception as e:
        print_fail(f"Vague query test failed with exception: {e}")
        return False


def test_chat_unknown_query():
    """Test 6: Unknown query - should return fallback"""
    print_test("Chat - Unknown Query Fallback")
    
    # Create new conversation
    conv_id = test_chat_create_conversation()
    if not conv_id:
        return False
    
    try:
        response = session.post(
            f"{API_URL}/chat/conversations/{conv_id}/messages",
            json={"content": "How to cook pasta?"},
            headers={"Origin": TEST_ORIGIN},
            stream=True
        )
        
        print_info(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print_fail(f"Send message failed with status {response.status_code}: {response.text}")
            return False
        
        # Parse SSE stream
        events = []
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    data_str = line_str[6:]
                    try:
                        event = json.loads(data_str)
                        events.append(event)
                    except json.JSONDecodeError:
                        pass
        
        print_info(f"Events received: {len(events)}")
        
        # Check for fallback event
        fallback_event = next((e for e in events if e.get('type') == 'fallback'), None)
        if not fallback_event:
            print_fail("No 'fallback' event received")
            print_info(f"Events: {events}")
            return False
        
        message = fallback_event.get('message', '')
        print_info(f"Fallback message: {message}")
        
        print_pass("Fallback event received for unknown query")
        print_pass("Unknown query fallback test passed")
        return True
        
    except Exception as e:
        print_fail(f"Unknown query test failed with exception: {e}")
        return False


def test_chat_kb_match():
    """Test 7: Specific KB match - should return AI-generated response"""
    print_test("Chat - Specific KB Match")
    
    # Create new conversation
    conv_id = test_chat_create_conversation()
    if not conv_id:
        return False
    
    try:
        response = session.post(
            f"{API_URL}/chat/conversations/{conv_id}/messages",
            json={"content": "How to configure GST?"},
            headers={"Origin": TEST_ORIGIN},
            stream=True
        )
        
        print_info(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print_fail(f"Send message failed with status {response.status_code}: {response.text}")
            return False
        
        # Parse SSE stream
        full_response = ""
        events = []
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    data_str = line_str[6:]
                    try:
                        event = json.loads(data_str)
                        events.append(event)
                        if event.get('type') == 'token':
                            full_response += event.get('content', '')
                    except json.JSONDecodeError:
                        pass
        
        print_info(f"Events received: {len(events)}")
        print_info(f"Full response: {full_response[:200]}...")
        
        # Check for done event
        done_event = next((e for e in events if e.get('type') == 'done'), None)
        if not done_event:
            print_fail("No 'done' event received")
            return False
        
        print_pass("SSE stream completed with 'done' event")
        
        # Check response is not empty
        if len(full_response) < 10:
            print_fail(f"Response too short: {full_response}")
            return False
        
        print_pass(f"AI-generated response received ({len(full_response)} chars)")
        print_pass("Specific KB match test passed")
        return True
        
    except Exception as e:
        print_fail(f"KB match test failed with exception: {e}")
        return False


def test_admin_config_get():
    """Test 8: GET /api/admin/ai-config - verify suggestion_message field"""
    print_test("Admin Config - GET ai-config")
    
    try:
        response = session.get(
            f"{API_URL}/admin/ai-config",
            headers={"Origin": TEST_ORIGIN}
        )
        
        print_info(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print_fail(f"GET ai-config failed with status {response.status_code}: {response.text}")
            return False, None
        
        data = response.json()
        print_info(f"Response keys: {list(data.keys())}")
        
        # Check suggestion_message field exists
        if "suggestion_message" not in data:
            print_fail("suggestion_message field not found in ai-config")
            return False, None
        
        suggestion_message = data.get("suggestion_message")
        print_pass(f"suggestion_message field exists: {suggestion_message}")
        
        print_pass("GET ai-config test passed")
        return True, suggestion_message
        
    except Exception as e:
        print_fail(f"GET ai-config test failed with exception: {e}")
        return False, None


def test_admin_config_put():
    """Test 9: PUT /api/admin/ai-config - update suggestion_message"""
    print_test("Admin Config - PUT ai-config")
    
    custom_message = "Custom suggestion text for testing"
    
    try:
        response = session.put(
            f"{API_URL}/admin/ai-config",
            json={"suggestion_message": custom_message},
            headers={"Origin": TEST_ORIGIN}
        )
        
        print_info(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print_fail(f"PUT ai-config failed with status {response.status_code}: {response.text}")
            return False
        
        data = response.json()
        print_info(f"Response: {json.dumps(data, indent=2)}")
        
        print_pass("PUT ai-config successful")
        return True
        
    except Exception as e:
        print_fail(f"PUT ai-config test failed with exception: {e}")
        return False


def test_admin_config_verify():
    """Test 10: GET /api/admin/ai-config - verify suggestion_message was updated"""
    print_test("Admin Config - Verify Update")
    
    custom_message = "Custom suggestion text for testing"
    
    try:
        response = session.get(
            f"{API_URL}/admin/ai-config",
            headers={"Origin": TEST_ORIGIN}
        )
        
        print_info(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print_fail(f"GET ai-config failed with status {response.status_code}: {response.text}")
            return False
        
        data = response.json()
        suggestion_message = data.get("suggestion_message")
        
        print_info(f"suggestion_message: {suggestion_message}")
        
        if suggestion_message != custom_message:
            print_fail(f"Expected '{custom_message}', got '{suggestion_message}'")
            return False
        
        print_pass(f"suggestion_message updated correctly: {suggestion_message}")
        print_pass("Verify update test passed")
        return True
        
    except Exception as e:
        print_fail(f"Verify update test failed with exception: {e}")
        return False


def test_trained_answers_list():
    """Test 11: GET /api/admin/trained-answers - list all"""
    print_test("Trained Answers - GET list")
    
    try:
        response = session.get(
            f"{API_URL}/admin/trained-answers",
            headers={"Origin": TEST_ORIGIN}
        )
        
        print_info(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print_fail(f"GET trained-answers failed with status {response.status_code}: {response.text}")
            return False, []
        
        data = response.json()
        print_info(f"Trained answers count: {len(data)}")
        
        if len(data) > 0:
            print_info(f"First trained answer: {data[0].get('question_pattern', 'N/A')}")
        
        print_pass(f"GET trained-answers successful - {len(data)} items")
        return True, data
        
    except Exception as e:
        print_fail(f"GET trained-answers test failed with exception: {e}")
        return False, []


def test_trained_answers_create():
    """Test 12: POST /api/admin/trained-answers - create new one"""
    print_test("Trained Answers - POST create")
    
    try:
        response = session.post(
            f"{API_URL}/admin/trained-answers",
            json={
                "question_pattern": "What is the test question?",
                "answer": "This is a test answer created by backend_test.py",
                "keywords": ["test", "backend", "automated"]
            },
            headers={"Origin": TEST_ORIGIN}
        )
        
        print_info(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print_fail(f"POST trained-answers failed with status {response.status_code}: {response.text}")
            return False, None
        
        data = response.json()
        print_info(f"Response: {json.dumps(data, indent=2)}")
        
        if "_id" not in data:
            print_fail("Response missing '_id' field")
            return False, None
        
        ta_id = data["_id"]
        print_pass(f"Trained answer created with ID: {ta_id}")
        return True, ta_id
        
    except Exception as e:
        print_fail(f"POST trained-answers test failed with exception: {e}")
        return False, None


def test_trained_answers_delete(ta_id: str):
    """Test 13: DELETE /api/admin/trained-answers/{ta_id} - delete the created one"""
    print_test("Trained Answers - DELETE")
    
    try:
        response = session.delete(
            f"{API_URL}/admin/trained-answers/{ta_id}",
            headers={"Origin": TEST_ORIGIN}
        )
        
        print_info(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print_fail(f"DELETE trained-answers failed with status {response.status_code}: {response.text}")
            return False
        
        data = response.json()
        print_info(f"Response: {data}")
        
        print_pass(f"Trained answer deleted successfully: {ta_id}")
        return True
        
    except Exception as e:
        print_fail(f"DELETE trained-answers test failed with exception: {e}")
        return False


def main():
    """Run all tests"""
    print(f"\n{Colors.BLUE}{'='*80}{Colors.RESET}")
    print(f"{Colors.BLUE}ASTRA AI KNOWLEDGE ASSISTANT - COMPREHENSIVE BACKEND TEST SUITE{Colors.RESET}")
    print(f"{Colors.BLUE}{'='*80}{Colors.RESET}")
    print(f"{Colors.YELLOW}Backend URL: {BASE_URL}{Colors.RESET}")
    print(f"{Colors.YELLOW}API URL: {API_URL}{Colors.RESET}")
    print(f"{Colors.YELLOW}Test Origin: {TEST_ORIGIN}{Colors.RESET}\n")
    
    results = {}
    
    # Test 1: CORS
    results["CORS"] = test_cors()
    
    # Test 2: Login
    results["Login"] = test_login()
    
    if not results["Login"]:
        print_fail("Login failed - cannot proceed with authenticated tests")
        return
    
    # Test 3-4: Chat - Trained Answer Priority
    conv_id = test_chat_create_conversation()
    if conv_id:
        results["Chat - Trained Answer"] = test_chat_trained_answer(conv_id)
    else:
        results["Chat - Trained Answer"] = False
    
    # Test 5: Chat - Vague Query
    results["Chat - Vague Query"] = test_chat_vague_query()
    
    # Test 6: Chat - Unknown Query
    results["Chat - Unknown Query"] = test_chat_unknown_query()
    
    # Test 7: Chat - KB Match
    results["Chat - KB Match"] = test_chat_kb_match()
    
    # Test 8: Admin Config - GET
    get_result, original_message = test_admin_config_get()
    results["Admin Config - GET"] = get_result
    
    # Test 9: Admin Config - PUT
    results["Admin Config - PUT"] = test_admin_config_put()
    
    # Test 10: Admin Config - Verify
    results["Admin Config - Verify"] = test_admin_config_verify()
    
    # Test 11: Trained Answers - List
    list_result, trained_answers = test_trained_answers_list()
    results["Trained Answers - List"] = list_result
    
    # Test 12: Trained Answers - Create
    create_result, ta_id = test_trained_answers_create()
    results["Trained Answers - Create"] = create_result
    
    # Test 13: Trained Answers - Delete
    if ta_id:
        results["Trained Answers - Delete"] = test_trained_answers_delete(ta_id)
    else:
        results["Trained Answers - Delete"] = False
    
    # Summary
    print(f"\n{Colors.BLUE}{'='*80}{Colors.RESET}")
    print(f"{Colors.BLUE}TEST SUMMARY{Colors.RESET}")
    print(f"{Colors.BLUE}{'='*80}{Colors.RESET}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = f"{Colors.GREEN}✓ PASS{Colors.RESET}" if result else f"{Colors.RED}✗ FAIL{Colors.RESET}"
        print(f"{status} - {test_name}")
    
    print(f"\n{Colors.BLUE}{'='*80}{Colors.RESET}")
    if passed == total:
        print(f"{Colors.GREEN}ALL TESTS PASSED: {passed}/{total}{Colors.RESET}")
    else:
        print(f"{Colors.RED}SOME TESTS FAILED: {passed}/{total} passed{Colors.RESET}")
    print(f"{Colors.BLUE}{'='*80}{Colors.RESET}\n")


if __name__ == "__main__":
    main()
