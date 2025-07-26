import pytest
import requests
import json
import time
from datetime import datetime, timedelta

# Base URL for the Flask API
BASE_URL = "http://127.0.0.1:5000"

# --- Global Test Data (will be populated by fixtures) ---
# These will store IDs and tokens needed across tests
test_data = {
    "librarian_id": None,
    "librarian_username": "test_librarian",
    "librarian_password": "lib_password",
    "student_id": None,
    "student_username": "test_student",
    "student_password": "stud_password",
    "student_token": None,
    "book_ids": [],
    "borrow_records": []
}

# --- Helper Functions for API Calls ---
def make_request(method, endpoint, headers=None, data=None, params=None):
    """Helper function to make API requests and return JSON response or None on error."""
    url = f"{BASE_URL}{endpoint}"
    try:
        if method == 'GET':
            response = requests.get(url, headers=headers, params=params, timeout=10)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=data, timeout=10)
        elif method == 'PUT':
            response = requests.put(url, headers=headers, json=data, timeout=10)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers, timeout=10)
        else:
            pytest.fail(f"Unsupported HTTP method: {method}")
            return None

        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.ConnectionError:
        pytest.fail(f"Connection Error: Ensure Flask server is running at {BASE_URL}")
    except requests.exceptions.Timeout:
        pytest.fail(f"Request timed out after 10 seconds for {method} {url}")
    except requests.exceptions.HTTPError as e:
        # For 4xx/5xx errors, try to return the error JSON if available
        try:
            return e.response.json()
        except json.JSONDecodeError:
            pytest.fail(f"HTTP Error {e.response.status_code}: {e.response.text}")
    except json.JSONDecodeError:
        pytest.fail(f"Invalid JSON response for {method} {url}: {response.text}")
    except Exception as e:
        pytest.fail(f"An unexpected error occurred during API call: {e}")
    return None

# --- Pytest Fixtures ---

@pytest.fixture(scope="session", autouse=True)
def setup_users():
    """
    Registers and logs in a librarian and a student,
    storing their IDs and tokens for other tests.
    Runs once per test session.
    """
    print(f"\n--- Setting up users for the test session ---")

    # Register Librarian
    res = make_request('POST', '/register', data={
        "username": test_data["librarian_username"],
        "password": test_data["librarian_password"],
        "role": "librarian"
    }, headers={"Content-Type": "application/json"})
    assert res is not None
    assert res['message'] in ["Librarian registered successfully", "Librarian already registered"]
    test_data["librarian_id"] = res['user_id']
    print(f"Librarian ID: {test_data['librarian_id']}")

    # Register Student
    res = make_request('POST', '/register', data={
        "username": test_data["student_username"],
        "password": test_data["student_password"],
        "role": "student"
    }, headers={"Content-Type": "application/json"})
    assert res is not None
    assert res['message'] in ["Student registered successfully", "Student already registered", "Student already registered, token generated"]
    test_data["student_id"] = res['user_id']
    test_data["student_token"] = res['token']
    print(f"Student ID: {test_data['student_id']}, Token: {test_data['student_token']}")

    assert test_data["librarian_id"] is not None
    assert test_data["student_id"] is not None
    assert test_data["student_token"] is not None

    # Verify login
    login_lib_res = make_request('POST', '/login', data={
        "username": test_data["librarian_username"],
        "password": test_data["librarian_password"]
    }, headers={"Content-Type": "application/json"})
    assert login_lib_res and login_lib_res['message'] == "Login successful"

    login_stud_res = make_request('POST', '/login', data={
        "username": test_data["student_username"],
        "password": test_data["student_password"]
    }, headers={"Content-Type": "application/json"})
    assert login_stud_res and login_stud_res['message'] == "Login successful"
    assert login_stud_res['token'] == test_data["student_token"]

    yield # Yield control to tests

    print(f"\n--- Tearing down test session (optional cleanup) ---")
    # In a real system, you might delete test data here.
    # For CSVs, this would mean reloading/clearing the CSVs, which is complex for a simple fixture.
    # For this example, we assume the CSVs are managed externally or for a fresh run.

@pytest.fixture(scope="function", autouse=False)
def add_test_book():
    """Fixture to add a book for individual test cases and clean it up."""
    book_data = {
        "title": f"Test Book {datetime.now().strftime('%H%M%S%f')}",
        "author": "Test Author",
        "isbn": f"TEST-{int(time.time() * 1000)}",
        "publication_year": 2023,
        "total_copies": 1
    }
    res = make_request('POST', '/books', headers={
        "X-User-ID": str(test_data["librarian_id"]),
        "Content-Type": "application/json"
    }, data=book_data)
    assert res is not None and res['message'] == "Book added successfully"
    book_id = res['book']['id']
    test_data["book_ids"].append(book_id) # Track book for potential cleanup if needed

    yield book_id

    # Cleanup: Delete the book after the test
    # Note: Deleting might fail if the book is still borrowed/reserved by a test
    # For robust cleanup, you'd need to ensure all related records are cleared first.
    # For simplicity, we'll just try to delete.
    try:
        make_request('DELETE', f'/books/{book_id}', headers={
            "X-User-ID": str(test_data["librarian_id"])
        })
    except Exception as e:
        print(f"Warning: Could not delete book {book_id} during cleanup: {e}")


# --- Functional Test Scenarios ---

class TestFunctional:

    # --- Registration & Login ---
    def test_register_new_librarian(self):
        username = "new_librarian_func"
        password = "new_lib_pass"
        res = make_request('POST', '/register', data={"username": username, "password": password, "role": "librarian"})
        assert res is not None
        assert res['message'] == "Librarian registered successfully"
        assert 'user_id' in res

    def test_register_existing_librarian_fails(self):
        # Use the librarian from setup_users
        res = make_request('POST', '/register', data={
            "username": test_data["librarian_username"],
            "password": test_data["librarian_password"],
            "role": "librarian"
        })
        assert res is not None
        assert res['message'] == "Librarian already registered"
        assert res['user_id'] == test_data["librarian_id"]

    def test_register_new_student(self):
        username = "new_student_func"
        password = "new_stud_pass"
        res = make_request('POST', '/register', data={"username": username, "password": password, "role": "student"})
        assert res is not None
        assert res['message'] == "Student registered successfully"
        assert 'user_id' in res
        assert 'token' in res

    def test_register_existing_student_returns_token(self):
        # Use the student from setup_users
        res = make_request('POST', '/register', data={
            "username": test_data["student_username"],
            "password": test_data["student_password"],
            "role": "student"
        })
        assert res is not None
        assert res['message'] in ["Student already registered", "Student already registered, token generated"]
        assert res['user_id'] == test_data["student_id"]
        assert res['token'] == test_data["student_token"]

    def test_login_valid_librarian(self):
        res = make_request('POST', '/login', data={
            "username": test_data["librarian_username"],
            "password": test_data["librarian_password"]
        })
        assert res is not None
        assert res['message'] == "Login successful"
        assert res['user_id'] == test_data["librarian_id"]
        assert res['role'] == "librarian"

    def test_login_valid_student(self):
        res = make_request('POST', '/login', data={
            "username": test_data["student_username"],
            "password": test_data["student_password"]
        })
        assert res is not None
        assert res['message'] == "Login successful"
        assert res['user_id'] == test_data["student_id"]
        assert res['role'] == "student"
        assert res['token'] == test_data["student_token"]

    def test_login_invalid_credentials(self):
        res = make_request('POST', '/login', data={"username": "wrong_user", "password": "wrong_pass"})
        assert res is not None
        assert res['message'] == "Invalid username or password"

    def test_login_missing_credentials(self):
        res = make_request('POST', '/login', data={"username": "test_user"})
        assert res is not None
        assert res['message'] == "Missing username or password"

    # --- Book Management (Librarian) ---
    def test_librarian_add_book_positive(self):
        book_data = {
            "title": "New Python Book",
            "author": "Pythonista",
            "isbn": "978-1234567890",
            "publication_year": 2024,
            "total_copies": 5
        }
        res = make_request('POST', '/books', headers={
            "X-User-ID": str(test_data["librarian_id"]),
            "Content-Type": "application/json"
        }, data=book_data)
        assert res is not None
        assert res['message'] == "Book added successfully"
        assert res['book']['title'] == book_data['title']
        assert res['book']['available_copies'] == book_data['total_copies']
        test_data["book_ids"].append(res['book']['id']) # Store for potential cleanup

    def test_librarian_add_book_missing_fields(self):
        book_data = {"title": "Incomplete Book", "author": "Anon"} # Missing ISBN
        res = make_request('POST', '/books', headers={
            "X-User-ID": str(test_data["librarian_id"]),
            "Content-Type": "application/json"
        }, data=book_data)
        assert res is not None
        assert res['message'] == "Missing required book details (title, author, isbn)"

    def test_librarian_add_book_duplicate_isbn(self):
        # Add a book first
        book_data_orig = {
            "title": "Duplicate ISBN Test",
            "author": "Test",
            "isbn": "978-1111111111",
            "total_copies": 1
        }
        make_request('POST', '/books', headers={
            "X-User-ID": str(test_data["librarian_id"]),
            "Content-Type": "application/json"
        }, data=book_data_orig)

        # Try to add again with same ISBN
        book_data_dup = {
            "title": "Another Duplicate ISBN Test",
            "author": "Test",
            "isbn": "978-1111111111",
            "total_copies": 1
        }
        res = make_request('POST', '/books', headers={
            "X-User-ID": str(test_data["librarian_id"]),
            "Content-Type": "application/json"
        }, data=book_data_dup)
        assert res is not None
        assert res['message'] == "Book with this ISBN already exists"

    def test_student_cannot_add_book(self):
        book_data = {"title": "Forbidden Book", "author": "Evil", "isbn": "999-9999999999", "total_copies": 1}
        res = make_request('POST', '/books', headers={
            "X-Auth-Token": test_data["student_token"],
            "Content-Type": "application/json"
        }, data=book_data)
        assert res is not None
        assert res['message'] == "Access denied: librarian role required"

    def test_get_all_books(self):
        res = make_request('GET', '/books', headers={"X-Auth-Token": test_data["student_token"]})
        assert res is not None
        assert isinstance(res, list)
        assert len(res) > 0 # Should have at least the books added by fixtures/other tests

    def test_get_books_filtered_by_title(self):
        # Ensure a specific book exists for filtering
        book_id = add_test_book()
        res = make_request('GET', '/books', headers={"X-Auth-Token": test_data["student_token"]}, params={"title": "Test Book"})
        assert res is not None
        assert isinstance(res, list)
        assert len(res) >= 1
        assert any("Test Book" in book['title'] for book in res)

    def test_get_book_details_positive(self, add_test_book):
        book_id = add_test_book
        res = make_request('GET', f'/books/{book_id}', headers={"X-Auth-Token": test_data["student_token"]})
        assert res is not None
        assert res['id'] == book_id
        assert 'title' in res

    def test_get_book_details_non_existent(self):
        res = make_request('GET', '/books/999999', headers={"X-Auth-Token": test_data["student_token"]})
        assert res is not None
        assert res['message'] == "Book not found"

    def test_librarian_update_book_positive(self, add_test_book):
        book_id = add_test_book
        updates = {"title": "Updated Title", "publication_year": 2025}
        res = make_request('PUT', f'/books/{book_id}', headers={
            "X-User-ID": str(test_data["librarian_id"]),
            "Content-Type": "application/json"
        }, data=updates)
        assert res is not None
        assert res['message'] == "Book updated successfully"
        assert res['book']['title'] == "Updated Title"
        assert res['book']['publication_year'] == 2025

    def test_librarian_update_book_change_total_copies(self, add_test_book):
        book_id = add_test_book
        # First, get current copies
        book_details = make_request('GET', f'/books/{book_id}', headers={"X-User-ID": str(test_data["librarian_id"])})
        initial_total = book_details['total_copies']
        initial_available = book_details['available_copies']

        # Update total copies to more
        new_total = initial_total + 2
        res = make_request('PUT', f'/books/{book_id}', headers={
            "X-User-ID": str(test_data["librarian_id"]),
            "Content-Type": "application/json"
        }, data={"total_copies": new_total})
        assert res is not None
        assert res['message'] == "Book updated successfully"
        assert res['book']['total_copies'] == new_total
        assert res['book']['available_copies'] == initial_available + 2

    def test_librarian_update_book_reduce_total_copies_below_borrowed_fails(self, add_test_book):
        book_id = add_test_book
        # Borrow the book first
        borrow_res = make_request('POST', f'/borrow/{book_id}', headers={
            "X-Auth-Token": test_data["student_token"],
            "Content-Type": "application/json"
        })
        assert borrow_res and borrow_res['message'] == "Book borrowed successfully"

        # Try to reduce total copies to less than borrowed
        # Assuming initial total was 1, and 1 is borrowed, trying to set total_copies to 0 should fail
        res = make_request('PUT', f'/books/{book_id}', headers={
            "X-User-ID": str(test_data["librarian_id"]),
            "Content-Type": "application/json"
        }, data={"total_copies": 0})
        assert res is not None
        assert res['message'] == "Cannot reduce total copies below currently borrowed copies"

        # Cleanup borrowed record for subsequent tests/cleanup
        borrow_record_id = borrow_res['record']['id']
        make_request('POST', f'/return/{borrow_record_id}', headers={
            "X-User-ID": str(test_data["librarian_id"]),
            "Content-Type": "application/json"
        })


    def test_librarian_delete_book_positive(self):
        # Add a book specifically for deletion
        book_data = {
            "title": "Book to Delete",
            "author": "Deleter",
            "isbn": f"DEL-{int(time.time() * 1000)}",
            "total_copies": 1
        }
        add_res = make_request('POST', '/books', headers={
            "X-User-ID": str(test_data["librarian_id"]),
            "Content-Type": "application/json"
        }, data=book_data)
        assert add_res and add_res['message'] == "Book added successfully"
        book_id_to_delete = add_res['book']['id']

        # Delete it
        del_res = make_request('DELETE', f'/books/{book_id_to_delete}', headers={
            "X-User-ID": str(test_data["librarian_id"])
        })
        assert del_res is not None
        assert del_res['message'] == "Book deleted successfully"

        # Verify it's gone
        get_res = make_request('GET', f'/books/{book_id_to_delete}', headers={"X-Auth-Token": test_data["student_token"]})
        assert get_res is not None
        assert get_res['message'] == "Book not found"

    def test_librarian_delete_book_with_active_records_fails(self, add_test_book):
        book_id = add_test_book
        # Borrow the book to create an active record
        borrow_res = make_request('POST', f'/borrow/{book_id}', headers={
            "X-Auth-Token": test_data["student_token"],
            "Content-Type": "application/json"
        })
        assert borrow_res and borrow_res['message'] == "Book borrowed successfully"

        # Try to delete
        del_res = make_request('DELETE', f'/books/{book_id}', headers={
            "X-User-ID": str(test_data["librarian_id"])
        })
        assert del_res is not None
        assert del_res['message'] == "Cannot delete book: active borrowing or reservation records exist"

        # Cleanup borrowed record
        borrow_record_id = borrow_res['record']['id']
        make_request('POST', f'/return/{borrow_record_id}', headers={
            "X-User-ID": str(test_data["librarian_id"]),
            "Content-Type": "application/json"
        })

    # --- Student Borrowing/Reservation ---
    def test_student_borrow_book_positive(self, add_test_book):
        book_id = add_test_book
        res = make_request('POST', f'/borrow/{book_id}', headers={
            "X-Auth-Token": test_data["student_token"],
            "Content-Type": "application/json"
        })
        assert res is not None
        assert res['message'] == "Book borrowed successfully"
        assert 'record' in res
        assert res['record']['book_id'] == book_id
        assert res['record']['student_id'] == test_data["student_id"]
        assert res['record']['status'] == 'borrowed'
        assert 'borrow_date' in res['record']
        assert 'due_date' in res['record']
        test_data["borrow_records"].append(res['record']['id']) # Store for cleanup

    def test_student_borrow_book_unavailable(self):
        # Add a book with 0 copies
        book_data = {
            "title": "Unavailable Book",
            "author": "No Copies",
            "isbn": f"UNAVAIL-{int(time.time() * 1000)}",
            "total_copies": 0
        }
        add_res = make_request('POST', '/books', headers={
            "X-User-ID": str(test_data["librarian_id"]),
            "Content-Type": "application/json"
        }, data=book_data)
        assert add_res and add_res['message'] == "Book added successfully"
        book_id = add_res['book']['id']

        res = make_request('POST', f'/borrow/{book_id}', headers={
            "X-Auth-Token": test_data["student_token"],
            "Content-Type": "application/json"
        })
        assert res is not None
        assert res['message'] == "No copies of this book are currently available"

    def test_student_borrow_max_limit(self, add_test_book):
        # Borrow 3 books first
        book_ids_for_limit = []
        borrow_record_ids = []
        for i in range(3):
            book_data = {
                "title": f"Limit Book {i}",
                "author": "Limit Author",
                "isbn": f"LIMIT-{int(time.time() * 1000)}-{i}",
                "total_copies": 1
            }
            add_res = make_request('POST', '/books', headers={
                "X-User-ID": str(test_data["librarian_id"]),
                "Content-Type": "application/json"
            }, data=book_data)
            assert add_res and add_res['message'] == "Book added successfully"
            book_id = add_res['book']['id']
            book_ids_for_limit.append(book_id)

            borrow_res = make_request('POST', f'/borrow/{book_id}', headers={
                "X-Auth-Token": test_data["student_token"],
                "Content-Type": "application/json"
            })
            assert borrow_res and borrow_res['message'] == "Book borrowed successfully"
            borrow_record_ids.append(borrow_res['record']['id'])
        
        # Try to borrow a 4th book
        book_data_4th = {
            "title": "Fourth Limit Book",
            "author": "Limit Author",
            "isbn": f"LIMIT-4TH-{int(time.time() * 1000)}",
            "total_copies": 1
        }
        add_res_4th = make_request('POST', '/books', headers={
            "X-User-ID": str(test_data["librarian_id"]),
            "Content-Type": "application/json"
        }, data=book_data_4th)
        assert add_res_4th and add_res_4th['message'] == "Book added successfully"
        book_id_4th = add_res_4th['book']['id']

        res = make_request('POST', f'/borrow/{book_id_4th}', headers={
            "X-Auth-Token": test_data["student_token"],
            "Content-Type": "application/json"
        })
        assert res is not None
        assert res['message'] == "You have reached the maximum limit of 3 borrowed books"

        # Cleanup: Return all borrowed books
        for record_id in borrow_record_ids:
            make_request('POST', f'/return/{record_id}', headers={
                "X-User-ID": str(test_data["librarian_id"]),
                "Content-Type": "application/json"
            })
        # Clean up the 4th book as well
        make_request('DELETE', f'/books/{book_id_4th}', headers={"X-User-ID": str(test_data["librarian_id"])})
        for bid in book_ids_for_limit:
             make_request('DELETE', f'/books/{bid}', headers={"X-User-ID": str(test_data["librarian_id"])})


    def test_student_borrow_already_borrowed(self, add_test_book):
        book_id = add_test_book
        # Borrow first
        borrow_res = make_request('POST', f'/borrow/{book_id}', headers={
            "X-Auth-Token": test_data["student_token"],
            "Content-Type": "application/json"
        })
        assert borrow_res and borrow_res['message'] == "Book borrowed successfully"

        # Try to borrow again
        res = make_request('POST', f'/borrow/{book_id}', headers={
            "X-Auth-Token": test_data["student_token"],
            "Content-Type": "application/json"
        })
        assert res is not None
        assert res['message'] == "You have already borrowed this book"

        # Cleanup
        borrow_record_id = borrow_res['record']['id']
        make_request('POST', f'/return/{borrow_record_id}', headers={
            "X-User-ID": str(test_data["librarian_id"]),
            "Content-Type": "application/json"
        })

    def test_student_reserve_book_positive(self, add_test_book):
        book_id = add_test_book
        res = make_request('POST', f'/reserve/{book_id}', headers={
            "X-Auth-Token": test_data["student_token"],
            "Content-Type": "application/json"
        })
        assert res is not None
        assert res['message'] == "Book reserved successfully"
        assert 'record' in res
        assert res['record']['book_id'] == book_id
        assert res['record']['student_id'] == test_data["student_id"]
        assert res['record']['status'] == 'reserved'
        test_data["borrow_records"].append(res['record']['id']) # Store for cleanup

    def test_student_reserve_already_reserved(self, add_test_book):
        book_id = add_test_book
        # Reserve first
        reserve_res = make_request('POST', f'/reserve/{book_id}', headers={
            "X-Auth-Token": test_data["student_token"],
            "Content-Type": "application/json"
        })
        assert reserve_res and reserve_res['message'] == "Book reserved successfully"

        # Try to reserve again
        res = make_request('POST', f'/reserve/{book_id}', headers={
            "X-Auth-Token": test_data["student_token"],
            "Content-Type": "application/json"
        })
        assert res is not None
        assert res['message'] == "You have already borrowed or reserved this book"

        # Cleanup
        reserve_record_id = reserve_res['record']['id']
        make_request('POST', f'/return/{reserve_record_id}', headers={ # Librarian returns (cancels)
            "X-User-ID": str(test_data["librarian_id"]),
            "Content-Type": "application/json"
        })

    def test_student_borrow_reserved_book_collects_it(self, add_test_book):
        book_id = add_test_book
        # Reserve the book
        reserve_res = make_request('POST', f'/reserve/{book_id}', headers={
            "X-Auth-Token": test_data["student_token"],
            "Content-Type": "application/json"
        })
        assert reserve_res and reserve_res['message'] == "Book reserved successfully"
        reserve_record_id = reserve_res['record']['id']

        # Now try to borrow it (should convert reservation to borrowed)
        borrow_res = make_request('POST', f'/borrow/{book_id}', headers={
            "X-Auth-Token": test_data["student_token"],
            "Content-Type": "application/json"
        })
        assert borrow_res is not None
        assert borrow_res['message'] == "Reserved book collected and borrowed successfully"
        assert borrow_res['record']['id'] == reserve_record_id # Should be the same record
        assert borrow_res['record']['status'] == 'borrowed'
        assert 'borrow_date' in borrow_res['record']
        assert 'due_date' in borrow_res['record']

        # Cleanup
        make_request('POST', f'/return/{reserve_record_id}', headers={
            "X-User-ID": str(test_data["librarian_id"]),
            "Content-Type": "application/json"
        })

    def test_student_cancel_reservation_positive(self):
        # Add a book and reserve it
        book_data = {
            "title": "Book for Cancellation",
            "author": "Cancel Test",
            "isbn": f"CANCEL-{int(time.time() * 1000)}",
            "total_copies": 1
        }
        add_res = make_request('POST', '/books', headers={
            "X-User-ID": str(test_data["librarian_id"]),
            "Content-Type": "application/json"
        }, data=book_data)
        assert add_res and add_res['message'] == "Book added successfully"
        book_id = add_res['book']['id']

        reserve_res = make_request('POST', f'/reserve/{book_id}', headers={
            "X-Auth-Token": test_data["student_token"],
            "Content-Type": "application/json"
        })
        assert reserve_res and reserve_res['message'] == "Book reserved successfully"
        reserve_record_id = reserve_res['record']['id']

        # Cancel the reservation
        cancel_res = make_request('POST', f'/cancel_reservation/{reserve_record_id}', headers={
            "X-Auth-Token": test_data["student_token"],
            "Content-Type": "application/json"
        })
        assert cancel_res is not None
        assert cancel_res['message'] == "Reservation cancelled successfully"
        assert cancel_res['record']['status'] == 'cancelled'

        # Verify status
        my_books_res = make_request('GET', '/my_books', headers={"X-Auth-Token": test_data["student_token"]})
        assert not any(rec['id'] == reserve_record_id for rec in my_books_res) # Should not appear in active list

        # Cleanup book
        make_request('DELETE', f'/books/{book_id}', headers={"X-User-ID": str(test_data["librarian_id"])})


    def test_student_cancel_non_existent_reservation(self):
        res = make_request('POST', '/cancel_reservation/999999', headers={
            "X-Auth-Token": test_data["student_token"],
            "Content-Type": "application/json"
        })
        assert res is not None
        assert res['message'] == "Reservation record not found or does not belong to you"

    def test_student_cancel_borrowed_book_fails(self, add_test_book):
        book_id = add_test_book
        # Borrow the book
        borrow_res = make_request('POST', f'/borrow/{book_id}', headers={
            "X-Auth-Token": test_data["student_token"],
            "Content-Type": "application/json"
        })
        assert borrow_res and borrow_res['message'] == "Book borrowed successfully"
        borrow_record_id = borrow_res['record']['id']

        # Try to cancel (should fail)
        res = make_request('POST', f'/cancel_reservation/{borrow_record_id}', headers={
            "X-Auth-Token": test_data["student_token"],
            "Content-Type": "application/json"
        })
        assert res is not None
        assert res['message'] == "Only reserved books can be cancelled"

        # Cleanup
        make_request('POST', f'/return/{borrow_record_id}', headers={
            "X-User-ID": str(test_data["librarian_id"]),
            "Content-Type": "application/json"
        })

    def test_get_my_books_positive(self, add_test_book):
        book_id = add_test_book
        # Borrow a book
        borrow_res = make_request('POST', f'/borrow/{book_id}', headers={
            "X-Auth-Token": test_data["student_token"],
            "Content-Type": "application/json"
        })
        assert borrow_res and borrow_res['message'] == "Book borrowed successfully"
        borrow_record_id = borrow_res['record']['id']

        res = make_request('GET', '/my_books', headers={"X-Auth-Token": test_data["student_token"]})
        assert res is not None
        assert isinstance(res, list)
        assert any(rec['id'] == borrow_record_id for rec in res)

        # Cleanup
        make_request('POST', f'/return/{borrow_record_id}', headers={
            "X-User-ID": str(test_data["librarian_id"]),
            "Content-Type": "application/json"
        })

    # --- Librarian Return & View All Borrowed ---
    def test_librarian_return_book_positive(self, add_test_book):
        book_id = add_test_book
        # Borrow the book first
        borrow_res = make_request('POST', f'/borrow/{book_id}', headers={
            "X-Auth-Token": test_data["student_token"],
            "Content-Type": "application/json"
        })
        assert borrow_res and borrow_res['message'] == "Book borrowed successfully"
        borrow_record_id = borrow_res['record']['id']

        # Return it
        return_res = make_request('POST', f'/return/{borrow_record_id}', headers={
            "X-User-ID": str(test_data["librarian_id"]),
            "Content-Type": "application/json"
        })
        assert return_res is not None
        assert return_res['message'] == "Book returned successfully"
        assert return_res['record']['status'] == 'returned'
        assert 'return_date' in return_res['record']

        # Verify book copies incremented
        book_details = make_request('GET', f'/books/{book_id}', headers={"X-Auth-Token": test_data["student_token"]})
        assert book_details['available_copies'] == book_details['total_copies']

    def test_librarian_return_non_existent_record(self):
        res = make_request('POST', '/return/999999', headers={
            "X-User-ID": str(test_data["librarian_id"]),
            "Content-Type": "application/json"
        })
        assert res is not None
        assert res['message'] == "Borrowing record not found"

    def test_librarian_return_already_returned_fails(self, add_test_book):
        book_id = add_test_book
        # Borrow and return first
        borrow_res = make_request('POST', f'/borrow/{book_id}', headers={
            "X-Auth-Token": test_data["student_token"],
            "Content-Type": "application/json"
        })
        assert borrow_res and borrow_res['message'] == "Book borrowed successfully"
        borrow_record_id = borrow_res['record']['id']

        return_res = make_request('POST', f'/return/{borrow_record_id}', headers={
            "X-User-ID": str(test_data["librarian_id"]),
            "Content-Type": "application/json"
        })
        assert return_res and return_res['message'] == "Book returned successfully"

        # Try to return again
        res = make_request('POST', f'/return/{borrow_record_id}', headers={
            "X-User-ID": str(test_data["librarian_id"]),
            "Content-Type": "application/json"
        })
        assert res is not None
        assert res['message'] == "Book is not currently borrowed or reserved"

    def test_librarian_get_all_borrowed_books(self, add_test_book):
        book_id = add_test_book
        # Borrow a book to ensure there's an active record
        borrow_res = make_request('POST', f'/borrow/{book_id}', headers={
            "X-Auth-Token": test_data["student_token"],
            "Content-Type": "application/json"
        })
        assert borrow_res and borrow_res['message'] == "Book borrowed successfully"
        borrow_record_id = borrow_res['record']['id']

        res = make_request('GET', '/borrowed_books', headers={"X-User-ID": str(test_data["librarian_id"])})
        assert res is not None
        assert isinstance(res, list)
        assert any(rec['id'] == borrow_record_id for rec in res)
        assert any(rec['book_details']['id'] == book_id for rec in res)
        assert any(rec['student_details']['id'] == test_data["student_id"] for rec in res)

        # Cleanup
        make_request('POST', f'/return/{borrow_record_id}', headers={
            "X-User-ID": str(test_data["librarian_id"]),
            "Content-Type": "application/json"
        })

# --- Non-Functional Test Scenarios (Performance/Load) ---

class TestPerformance:

    NUM_REQUESTS = 100 # Number of requests for basic load test
    CONCURRENT_USERS = 5 # Simulate this many concurrent users for some tests

    def test_get_books_performance(self):
        """Measures average response time for getting all books."""
        total_time = 0
        for _ in range(self.NUM_REQUESTS):
            start_time = time.perf_counter()
            res = make_request('GET', '/books', headers={"X-Auth-Token": test_data["student_token"]})
            end_time = time.perf_counter()
            assert res is not None
            total_time += (end_time - start_time)
        
        avg_time = total_time / self.NUM_REQUESTS
        print(f"\nPerformance: Average response time for GET /books ({self.NUM_REQUESTS} requests): {avg_time:.4f} seconds")
        pytest.assume(avg_time < 0.5, f"GET /books average response time too high: {avg_time:.4f}s") # Example threshold

    def test_borrow_book_performance(self):
        """Measures average response time for borrowing a book (requires unique books)."""
        # Add enough books for the test
        book_ids_for_perf = []
        for i in range(self.NUM_REQUESTS):
            book_data = {
                "title": f"Perf Book {i}",
                "author": "Perf Author",
                "isbn": f"PERF-{int(time.time() * 1000)}-{i}",
                "total_copies": 1
            }
            add_res = make_request('POST', '/books', headers={
                "X-User-ID": str(test_data["librarian_id"]),
                "Content-Type": "application/json"
            }, data=book_data)
            assert add_res and add_res['message'] == "Book added successfully"
            book_ids_for_perf.append(add_res['book']['id'])

        total_time = 0
        borrow_record_ids = []
        for book_id in book_ids_for_perf:
            start_time = time.perf_counter()
            # Note: This is sequential. For true concurrency, use threading/asyncio or a load testing tool.
            res = make_request('POST', f'/borrow/{book_id}', headers={
                "X-Auth-Token": test_data["student_token"],
                "Content-Type": "application/json"
            })
            end_time = time.perf_counter()
            assert res is not None
            if res and 'record' in res:
                borrow_record_ids.append(res['record']['id'])
            total_time += (end_time - start_time)
        
        avg_time = total_time / self.NUM_REQUESTS
        print(f"\nPerformance: Average response time for POST /borrow (sequential {self.NUM_REQUESTS} requests): {avg_time:.4f} seconds")
        pytest.assume(avg_time < 0.8, f"POST /borrow average response time too high: {avg_time:.4f}s") # Example threshold

        # Cleanup: Return all borrowed books
        for record_id in borrow_record_ids:
            make_request('POST', f'/return/{record_id}', headers={
                "X-User-ID": str(test_data["librarian_id"]),
                "Content-Type": "application/json"
            })
        # Cleanup: Delete the books
        for book_id in book_ids_for_perf:
            make_request('DELETE', f'/books/{book_id}', headers={"X-User-ID": str(test_data["librarian_id"])})

    # Basic load test simulation (sequential, but demonstrates concept)
    def test_concurrent_get_books_simulation(self):
        """Simulates multiple 'users' getting books concurrently (sequentially in this simple test)."""
        all_times = []
        for user_idx in range(self.CONCURRENT_USERS):
            user_total_time = 0
            for _ in range(self.NUM_REQUESTS // self.CONCURRENT_USERS): # Distribute requests
                start_time = time.perf_counter()
                res = make_request('GET', '/books', headers={"X-Auth-Token": test_data["student_token"]})
                end_time = time.perf_counter()
                assert res is not None
                user_total_time += (end_time - start_time)
            all_times.append(user_total_time / (self.NUM_REQUESTS // self.CONCURRENT_USERS))
        
        overall_avg = sum(all_times) / len(all_times)
        print(f"\nLoad Test: Average response time per simulated user for GET /books ({self.CONCURRENT_USERS} users, {self.NUM_REQUESTS} total requests): {overall_avg:.4f} seconds")
        pytest.assume(overall_avg < 0.7, f"GET /books load test average response time too high: {overall_avg:.4f}s")


