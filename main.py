import requests
import json

BASE_URL = "http://127.0.0.1:5000"

def make_request(method, endpoint, headers=None, data=None, params=None):
    """Helper function to make API requests."""
    url = f"{BASE_URL}{endpoint}"
    print(f"\n--- {method} {url} ---")
    print(f"Headers: {headers}")
    print(f"Data: {data}")
    print(f"Params: {params}")

    try:
        if method == 'GET':
            response = requests.get(url, headers=headers, params=params)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=data)
        elif method == 'PUT':
            response = requests.put(url, headers=headers, json=data)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers)
        else:
            print(f"Unsupported method: {method}")
            return None

        print(f"Status Code: {response.status_code}")
        try:
            print(f"Response JSON: {json.dumps(response.json(), indent=2)}")
        except json.JSONDecodeError:
            print(f"Response Text: {response.text}")
        return response.json()
    except requests.exceptions.ConnectionError as e:
        print(f"Connection Error: {e}")
        print("Please ensure the Flask server is running at http://127.0.0.1:5000")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

# --- User Authentication ---
def register_user(username, password, role):
    endpoint = "/register"
    data = {"username": username, "password": password, "role": role}
    return make_request('POST', endpoint, data=data, headers={"Content-Type": "application/json"})

def login_user(username, password):
    endpoint = "/login"
    data = {"username": username, "password": password}
    return make_request('POST', endpoint, data=data, headers={"Content-Type": "application/json"})

# --- Book Management (Librarian Only) ---
def add_book(librarian_id, title, author, isbn, publication_year, total_copies):
    endpoint = "/books"
    headers = {"X-User-ID": str(librarian_id), "Content-Type": "application/json"}
    data = {
        "title": title,
        "author": author,
        "isbn": isbn,
        "publication_year": publication_year,
        "total_copies": total_copies
    }
    return make_request('POST', endpoint, headers=headers, data=data)

def get_books(user_id=None, auth_token=None, title=None, author=None, isbn=None):
    endpoint = "/books"
    headers = {}
    if user_id:
        headers["X-User-ID"] = str(user_id)
    if auth_token:
        headers["X-Auth-Token"] = auth_token
    
    params = {}
    if title:
        params["title"] = title
    if author:
        params["author"] = author
    if isbn:
        params["isbn"] = isbn

    return make_request('GET', endpoint, headers=headers, params=params)

def get_book_details(book_id, user_id=None, auth_token=None):
    endpoint = f"/books/{book_id}"
    headers = {}
    if user_id:
        headers["X-User-ID"] = str(user_id)
    if auth_token:
        headers["X-Auth-Token"] = auth_token
    return make_request('GET', endpoint, headers=headers)

def update_book(librarian_id, book_id, updates):
    endpoint = f"/books/{book_id}"
    headers = {"X-User-ID": str(librarian_id), "Content-Type": "application/json"}
    return make_request('PUT', endpoint, headers=headers, data=updates)

def delete_book(librarian_id, book_id):
    endpoint = f"/books/{book_id}"
    headers = {"X-User-ID": str(librarian_id)}
    return make_request('DELETE', endpoint, headers=headers)

# --- Student Actions ---
def borrow_book(student_token, book_id):
    endpoint = f"/borrow/{book_id}"
    headers = {"X-Auth-Token": student_token, "Content-Type": "application/json"}
    return make_request('POST', endpoint, headers=headers)

def reserve_book(student_token, book_id):
    endpoint = f"/reserve/{book_id}"
    headers = {"X-Auth-Token": student_token, "Content-Type": "application/json"}
    return make_request('POST', endpoint, headers=headers)

def cancel_reservation(student_token, borrow_id):
    endpoint = f"/cancel_reservation/{borrow_id}"
    headers = {"X-Auth-Token": student_token, "Content-Type": "application/json"}
    return make_request('POST', endpoint, headers=headers)

def get_my_books(student_token):
    endpoint = "/my_books"
    headers = {"X-Auth-Token": student_token}
    return make_request('GET', endpoint, headers=headers)

# --- Librarian Actions ---
def return_book(librarian_id, borrow_id):
    endpoint = f"/return/{borrow_id}"
    headers = {"X-User-ID": str(librarian_id), "Content-Type": "application/json"}
    return make_request('POST', endpoint, headers=headers)

def get_all_borrowed_books(librarian_id):
    endpoint = "/borrowed_books"
    headers = {"X-User-ID": str(librarian_id)}
    return make_request('GET', endpoint, headers=headers)

# --- Test Scenarios ---
def run_tests():
    print("--- Starting API Client Tests ---")

    # --- 1. Register Users ---
    print("\n### Registering Users ###")
    librarian_reg_res = register_user("librarian_alpha", "libpass", "librarian")
    librarian_id = librarian_reg_res['user_id'] if librarian_reg_res and 'user_id' in librarian_reg_res else None

    student_reg_res = register_user("student_beta", "studpass", "student")
    student_id = student_reg_res['user_id'] if student_reg_res and 'user_id' in student_reg_res else None
    student_token = student_reg_res['token'] if student_reg_res and 'token' in student_reg_res else None

    # Test re-registration for student (should return existing token)
    student_re_reg_res = register_user("student_beta", "studpass", "student")
    if student_re_reg_res and 'token' in student_re_reg_res:
        print(f"Student re-registration token: {student_re_reg_res['token']}")

    if not all([librarian_id, student_id, student_token]):
        print("Failed to register users or get tokens. Exiting tests.")
        return

    # --- 2. Login Users ---
    print("\n### Logging In Users ###")
    login_librarian_res = login_user("librarian_alpha", "libpass")
    login_student_res = login_user("student_beta", "studpass")

    # --- 3. Librarian Adds Books ---
    print("\n### Librarian Adding Books ###")
    book1_res = add_book(librarian_id, "The Hitchhiker's Guide to the Galaxy", "Douglas Adams", "978-0345391803", 1979, 3)
    book1_id = book1_res['book']['id'] if book1_res and 'book' in book1_res else None

    book2_res = add_book(librarian_id, "Pride and Prejudice", "Jane Austen", "978-0141439518", 1813, 2)
    book2_id = book2_res['book']['id'] if book2_res and 'book' in book2_res else None

    if not all([book1_id, book2_id]):
        print("Failed to add books. Exiting tests.")
        return

    # --- 4. Get Books (Student and Librarian) ---
    print("\n### Getting All Books ###")
    get_books(auth_token=student_token) # As student
    get_books(user_id=librarian_id) # As librarian

    print("\n### Getting Books with Filters ###")
    get_books(auth_token=student_token, title="hitchhiker")
    get_books(user_id=librarian_id, author="austen")
    get_books(auth_token=student_token, isbn="978-0345391803")

    # --- 5. Student Borrows Books ---
    print("\n### Student Borrowing Books ###")
    borrow1_res = borrow_book(student_token, book1_id)
    borrow1_id = borrow1_res['record']['id'] if borrow1_res and 'record' in borrow1_res else None

    borrow2_res = borrow_book(student_token, book2_id)
    borrow2_id = borrow2_res['record']['id'] if borrow2_res and 'record' in borrow2_res else None

    # Try to borrow a third book
    book3_res = add_book(librarian_id, "Dune", "Frank Herbert", "978-0441172719", 1965, 1)
    book3_id = book3_res['book']['id'] if book3_res and 'book' in book3_res else None
    if book3_id:
        borrow3_res = borrow_book(student_token, book3_id)
        borrow3_id = borrow3_res['record']['id'] if borrow3_res and 'record' in borrow3_res else None
    
    # Try to borrow a fourth book (should fail)
    print("\n### Attempting to borrow fourth book (should fail) ###")
    add_book(librarian_id, "The Lord of the Rings", "J.R.R. Tolkien", "978-0618053267", 1954, 1)
    borrow_book(student_token, 4) # Assuming book ID 4 is the new one

    # Try to borrow an unavailable book (should fail if available_copies is 0)
    print("\n### Attempting to borrow unavailable book (should fail) ###")
    # Make book2 unavailable by borrowing all copies
    add_book(librarian_id, "Another Book", "Another Author", "999-9999999999", 2000, 1)
    borrow_book(student_token, 5) # Assuming book ID 5 is "Another Book"
    
    # --- 6. Student Reserves a Book ---
    print("\n### Student Reserving a Book ###")
    reserve_book_res = reserve_book(student_token, book1_id) # Try to reserve book1 again (should fail as already borrowed)
    
    book4_res = add_book(librarian_id, "Foundation", "Isaac Asimov", "978-0553803717", 1951, 1)
    book4_id = book4_res['book']['id'] if book4_res and 'book' in book4_res else None
    if book4_id:
        reserve_book_res = reserve_book(student_token, book4_id)
        reserve_id = reserve_book_res['record']['id'] if reserve_book_res and 'record' in reserve_book_res else None

    # --- 7. Student Cancels Reservation ---
    if reserve_id:
        print(f"\n### Student Cancelling Reservation {reserve_id} ###")
        cancel_reservation(student_token, reserve_id)

    # --- 8. Get My Books (Student) ---
    print("\n### Getting Student's Borrowed/Reserved Books ###")
    get_my_books(student_token)

    # --- 9. Librarian Returns Books ---
    if borrow1_id:
        print(f"\n### Librarian Returning Book {borrow1_id} ###")
        return_book(librarian_id, borrow1_id)

    if borrow2_id:
        print(f"\n### Librarian Returning Book {borrow2_id} ###")
        return_book(librarian_id, borrow2_id)
    
    if borrow3_id:
        print(f"\n### Librarian Returning Book {borrow3_id} ###")
        return_book(librarian_id, borrow3_id)

    # --- 10. Librarian Gets All Borrowed Books (after returns) ---
    print("\n### Librarian Getting All Borrowed/Reserved Books (after returns) ###")
    get_all_borrowed_books(librarian_id)

    # --- 11. Librarian Updates Book ---
    print("\n### Librarian Updating Book ###")
    update_book(librarian_id, book1_id, {"publication_year": 1980, "total_copies": 4})

    # --- 12. Librarian Deletes Book ---
    print("\n### Librarian Deleting Book ###")
    # First, add a book that has no active borrowing records
    book_to_delete_res = add_book(librarian_id, "Ephemeral Novel", "Anon", "999-8888888888", 2020, 1)
    book_to_delete_id = book_to_delete_res['book']['id'] if book_to_delete_res and 'book' in book_to_delete_res else None
    if book_to_delete_id:
        delete_book(librarian_id, book_to_delete_id)

    # Try to delete a book with active records (should fail)
    print("\n### Attempting to delete book with active records (should fail) ###")
    borrow_book(student_token, book1_id) # Borrow book1 again to make it active
    delete_book(librarian_id, book1_id) # Should fail

    print("\n--- API Client Tests Finished ---")

if __name__ == "__main__":
    run_tests()
