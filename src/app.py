import os
import csv
from datetime import datetime, timedelta
from functools import wraps
import json # To handle serialization/deserialization of complex types in CSV if needed
import uuid # Added for generating unique tokens

from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here' # Replace with a strong, random key in production

# Define CSV file paths
DATA_DIR = os.path.join(app.instance_path, 'data')
USERS_CSV = os.path.join(DATA_DIR, 'users.csv')
BOOKS_CSV = os.path.join(DATA_DIR, 'books.csv')
BORROWING_RECORDS_CSV = os.path.join(DATA_DIR, 'borrowing_records.csv')

# Ensure the data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# --- CSV Helper Functions ---

def _read_csv(filepath):
    """Reads data from a CSV file and returns a list of dictionaries."""
    if not os.path.exists(filepath):
        return []
    with open(filepath, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        return list(reader)

def _write_csv(filepath, data, fieldnames):
    """Writes a list of dictionaries to a CSV file."""
    with open(filepath, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

def _get_next_id(data):
    """Generates the next available ID for a list of dictionaries."""
    if not data:
        return 1
    return max(int(item['id']) for item in data) + 1

# --- Data Loading and Initialization ---

# Global in-memory data stores (will be loaded from CSVs)
users_data = []
books_data = []
borrowing_records_data = []

def load_data():
    """Loads all data from CSV files into memory."""
    global users_data, books_data, borrowing_records_data
    users_data = _read_csv(USERS_CSV)
    books_data = _read_csv(BOOKS_CSV)
    borrowing_records_data = _read_csv(BORROWING_RECORDS_CSV)
    print("Data loaded from CSVs.")

def save_data():
    """Saves all in-memory data back to CSV files."""
    # Ensure 'token' is included in fieldnames for users_data
    _write_csv(USERS_CSV, users_data, ['id', 'username', 'password_hash', 'role', 'token'])
    _write_csv(BOOKS_CSV, books_data, ['id', 'title', 'author', 'isbn', 'publication_year', 'available_copies', 'total_copies'])
    _write_csv(BORROWING_RECORDS_CSV, borrowing_records_data, ['id', 'student_id', 'book_id', 'borrow_date', 'due_date', 'return_date', 'status'])
    print("Data saved to CSVs.")

# --- Helper Functions and Decorators ---

def is_working_day(date):
    """Checks if a given date is a working day (Monday-Friday)."""
    return date.weekday() < 5 # Monday is 0, Sunday is 6

def calculate_due_date(borrow_date, max_weeks=4):
    """
    Calculates the due date based on working days, up to a maximum of 4 weeks.
    """
    current_date = borrow_date
    working_days_count = 0
    # Max duration in calendar days (approx 4 weeks)
    max_calendar_days = max_weeks * 7

    for _ in range(max_calendar_days + 7): # Add buffer for weekends
        current_date += timedelta(days=1)
        if is_working_day(current_date):
            working_days_count += 1
        if working_days_count >= max_weeks * 5: # 5 working days per week
            break
    return current_date.replace(hour=23, minute=59, second=59, microsecond=999999) # End of day

def login_required(f):
    """
    Decorator to check if a user is logged in.
    Supports 'X-User-ID' for librarians and 'X-Auth-Token' for students.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id_header = request.headers.get('X-User-ID') # For librarians
        auth_token_header = request.headers.get('X-Auth-Token') # For students

        user = None
        if user_id_header:
            user = next((u for u in users_data if str(u['id']) == user_id_header), None)
        elif auth_token_header:
            user = next((u for u in users_data if u.get('token') == auth_token_header), None)

        if not user:
            return jsonify({"message": "Authentication required or invalid credentials"}), 401
        
        request.current_user = user # Attach user object (dictionary) to request
        return f(*args, **kwargs)
    return decorated_function

def role_required(role):
    """Decorator to check if the logged-in user has a specific role."""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if request.current_user['role'] != role:
                return jsonify({"message": f"Access denied: {role} role required"}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- API Endpoints ---

@app.route('/register', methods=['POST'])
def register_user():
    """
    Registers a new user (student or librarian).
    For students: if already registered, returns existing token; otherwise, creates and returns new token.
    For librarians: registers normally.
    Expects JSON: {"username": "...", "password": "...", "role": "student" or "librarian"}
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    role = data.get('role')

    if not username or not password or not role:
        return jsonify({"message": "Missing username, password, or role"}), 400
    
    if role not in ['student', 'librarian']:
        return jsonify({"message": "Invalid role. Must be 'student' or 'librarian'"}), 400

    existing_user = next((u for u in users_data if u['username'] == username), None)

    if role == 'student':
        if existing_user:
            # Student already registered
            if existing_user.get('token'):
                # Return existing token
                return jsonify({
                    "message": "Student already registered",
                    "user_id": int(existing_user['id']),
                    "role": existing_user['role'],
                    "token": existing_user['token']
                }), 200
            else:
                # Student exists but no token (e.g., registered before token feature)
                new_token = str(uuid.uuid4())
                existing_user['token'] = new_token
                save_data()
                return jsonify({
                    "message": "Student already registered, token generated",
                    "user_id": int(existing_user['id']),
                    "role": existing_user['role'],
                    "token": new_token
                }), 200
        else:
            # New student registration
            new_user_id = _get_next_id(users_data)
            new_token = str(uuid.uuid4()) # Generate a unique token for the student
            new_user = {
                'id': str(new_user_id), # Store ID as string for consistency with CSV
                'username': username,
                'password_hash': generate_password_hash(password),
                'role': role,
                'token': new_token # Store token for students
            }
            users_data.append(new_user)
            save_data()
            return jsonify({
                "message": f"{role.capitalize()} registered successfully",
                "user_id": int(new_user['id']),
                "token": new_user['token']
            }), 201
    elif role == 'librarian':
        if existing_user:
            return jsonify({"message": "Librarian already registered"}), 409 # No token for existing librarian, just inform
        else:
            new_user_id = _get_next_id(users_data)
            new_user = {
                'id': str(new_user_id),
                'username': username,
                'password_hash': generate_password_hash(password),
                'role': role,
                'token': '' # Librarians don't use tokens in this scheme, or can be omitted
            }
            users_data.append(new_user)
            save_data()
            return jsonify({
                "message": f"{role.capitalize()} registered successfully",
                "user_id": int(new_user['id'])
            }), 201
    else:
        return jsonify({"message": "Invalid role. Must be 'student' or 'librarian'"}), 400


@app.route('/login', methods=['POST'])
def login_user():
    """
    Logs in a user.
    Expects JSON: {"username": "...", "password": "..."}
    Returns user ID and role. For students, also returns the allocated token.
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"message": "Missing username or password"}), 400

    user = next((u for u in users_data if u['username'] == username), None)
    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({"message": "Invalid username or password"}), 401
    
    response_data = {"message": "Login successful", "user_id": int(user['id']), "role": user['role']}
    if user['role'] == 'student' and user.get('token'):
        response_data['token'] = user['token']
    
    return jsonify(response_data), 200

@app.route('/books', methods=['GET'])
@login_required
def get_books():
    """
    Retrieves a list of all books.
    Can be filtered by title, author, or ISBN via query parameters.
    """
    title = request.args.get('title')
    author = request.args.get('author')
    isbn = request.args.get('isbn')

    filtered_books = books_data

    if title:
        filtered_books = [b for b in filtered_books if title.lower() in b['title'].lower()]
    if author:
        filtered_books = [b for b in filtered_books if author.lower() in b['author'].lower()]
    if isbn:
        filtered_books = [b for b in filtered_books if b['isbn'] == isbn]

    # Convert numeric fields back to int for jsonify
    serializable_books = []
    for book in filtered_books:
        b = book.copy()
        b['id'] = int(b['id'])
        b['publication_year'] = int(b['publication_year']) if b.get('publication_year') else None
        b['available_copies'] = int(b['available_copies'])
        b['total_copies'] = int(b['total_copies'])
        serializable_books.append(b)

    return jsonify(serializable_books), 200

@app.route('/books', methods=['POST'])
@role_required('librarian')
def add_book():
    """
    Adds a new book to the library (Librarian only).
    Expects JSON: {"title": "...", "author": "...", "isbn": "...", "publication_year": ..., "total_copies": ...}
    """
    data = request.get_json()
    title = data.get('title')
    author = data.get('author')
    isbn = data.get('isbn')
    publication_year = data.get('publication_year')
    total_copies = data.get('total_copies', 0)

    if not all([title, author, isbn]):
        return jsonify({"message": "Missing required book details (title, author, isbn)"}), 400
    
    if any(b['isbn'] == isbn for b in books_data):
        return jsonify({"message": "Book with this ISBN already exists"}), 409

    new_book_id = _get_next_id(books_data)
    new_book = {
        'id': str(new_book_id),
        'title': title,
        'author': author,
        'isbn': isbn,
        'publication_year': str(publication_year) if publication_year else '', # Store as string
        'total_copies': str(total_copies),
        'available_copies': str(total_copies)
    }
    books_data.append(new_book)
    save_data()

    # Prepare response, converting numeric fields back to int
    response_book = new_book.copy()
    response_book['id'] = int(response_book['id'])
    response_book['publication_year'] = int(response_book['publication_year']) if response_book['publication_year'] else None
    response_book['available_copies'] = int(response_book['available_copies'])
    response_book['total_copies'] = int(response_book['total_copies'])

    return jsonify({"message": "Book added successfully", "book": response_book}), 201

@app.route('/books/<int:book_id>', methods=['GET'])
@login_required
def get_book_details(book_id):
    """
    Retrieves details for a specific book.
    """
    book_id_str = str(book_id)
    book = next((b for b in books_data if b['id'] == book_id_str), None)
    if not book:
        return jsonify({"message": "Book not found"}), 404
    
    # Convert numeric fields back to int for jsonify
    serializable_book = book.copy()
    serializable_book['id'] = int(serializable_book['id'])
    serializable_book['publication_year'] = int(serializable_book['publication_year']) if serializable_book['publication_year'] else None
    serializable_book['available_copies'] = int(serializable_book['available_copies'])
    serializable_book['total_copies'] = int(serializable_book['total_copies'])

    return jsonify(serializable_book), 200

@app.route('/books/<int:book_id>', methods=['PUT'])
@role_required('librarian')
def update_book(book_id):
    """
    Updates details for an existing book (Librarian only).
    Expects JSON with fields to update.
    """
    book_id_str = str(book_id)
    book_index = next((i for i, b in enumerate(books_data) if b['id'] == book_id_str), None)

    if book_index is None:
        return jsonify({"message": "Book not found"}), 404

    book = books_data[book_index]
    data = request.get_json()
    
    # Update fields if provided
    if 'title' in data:
        book['title'] = data['title']
    if 'author' in data:
        book['author'] = data['author']
    if 'isbn' in data:
        # Check for ISBN uniqueness if it's being changed
        if data['isbn'] != book['isbn'] and any(b['isbn'] == data['isbn'] for b in books_data if b['id'] != book_id_str):
            return jsonify({"message": "Book with this ISBN already exists"}), 409
        book['isbn'] = data['isbn']
    if 'publication_year' in data:
        book['publication_year'] = str(data['publication_year']) if data['publication_year'] else ''
    if 'total_copies' in data:
        new_total_copies = int(data['total_copies'])
        current_borrowed = int(book['total_copies']) - int(book['available_copies'])
        if new_total_copies < current_borrowed:
            return jsonify({"message": "Cannot reduce total copies below currently borrowed copies"}), 400
        book['available_copies'] = str(int(book['available_copies']) + (new_total_copies - int(book['total_copies'])))
        book['total_copies'] = str(new_total_copies)

    save_data()
    
    # Prepare response, converting numeric fields back to int
    response_book = book.copy()
    response_book['id'] = int(response_book['id'])
    response_book['publication_year'] = int(response_book['publication_year']) if response_book['publication_year'] else None
    response_book['available_copies'] = int(response_book['available_copies'])
    response_book['total_copies'] = int(response_book['total_copies'])

    return jsonify({"message": "Book updated successfully", "book": response_book}), 200

@app.route('/books/<int:book_id>', methods=['DELETE'])
@role_required('librarian')
def delete_book(book_id):
    """
    Deletes a book from the library (Librarian only).
    Only allowed if no active borrowing records exist for the book.
    """
    book_id_str = str(book_id)
    book_index = next((i for i, b in enumerate(books_data) if b['id'] == book_id_str), None)

    if book_index is None:
        return jsonify({"message": "Book not found"}), 404
    
    # Check for active borrowing records (borrowed or reserved)
    active_records = [
        rec for rec in borrowing_records_data 
        if rec['book_id'] == book_id_str and rec['status'] in ['borrowed', 'reserved']
    ]

    if active_records:
        return jsonify({"message": "Cannot delete book: active borrowing or reservation records exist"}), 400

    del books_data[book_index]
    save_data()
    return jsonify({"message": "Book deleted successfully"}), 200

@app.route('/borrow/<int:book_id>', methods=['POST'])
@role_required('student')
def borrow_book(book_id):
    """
    Allows a student to borrow a book (Student only).
    Checks max 3 books per student and availability.
    """
    student_id_str = request.current_user['id']
    book_id_str = str(book_id)

    book = next((b for b in books_data if b['id'] == book_id_str), None)
    if not book:
        return jsonify({"message": "Book not found"}), 404
    
    if int(book['available_copies']) <= 0:
        return jsonify({"message": "No copies of this book are currently available"}), 400
    
    # Check if student already has 3 books borrowed
    borrowed_count = sum(1 for rec in borrowing_records_data if rec['student_id'] == student_id_str and rec['status'] == 'borrowed')

    if borrowed_count >= 3:
        return jsonify({"message": "You have reached the maximum limit of 3 borrowed books"}), 400
    
    # Check if the student already has this specific book borrowed or reserved
    existing_record = next((
        rec for rec in borrowing_records_data 
        if rec['student_id'] == student_id_str and rec['book_id'] == book_id_str and rec['status'] in ['borrowed', 'reserved']
    ), None)

    if existing_record:
        if existing_record['status'] == 'borrowed':
            return jsonify({"message": "You have already borrowed this book"}), 400
        elif existing_record['status'] == 'reserved':
            # If reserved, convert reservation to borrowed
            existing_record['status'] = 'borrowed'
            existing_record['borrow_date'] = datetime.utcnow().isoformat()
            existing_record['due_date'] = calculate_due_date(datetime.utcnow()).isoformat()
            book['available_copies'] = str(int(book['available_copies']) - 1) # Decrement available copies
            save_data()
            # Prepare response
            response_record = existing_record.copy()
            response_record['id'] = int(response_record['id'])
            response_record['student_id'] = int(response_record['student_id'])
            response_record['book_id'] = int(response_record['book_id'])
            return jsonify({"message": "Reserved book collected and borrowed successfully", "record": response_record}), 200

    # Create new borrowing record
    borrow_date = datetime.utcnow()
    due_date = calculate_due_date(borrow_date)

    new_record_id = _get_next_id(borrowing_records_data)
    new_record = {
        'id': str(new_record_id),
        'student_id': student_id_str,
        'book_id': book_id_str,
        'borrow_date': borrow_date.isoformat(),
        'due_date': due_date.isoformat(),
        'return_date': '', # Empty string for null
        'status': 'borrowed'
    }
    borrowing_records_data.append(new_record)
    book['available_copies'] = str(int(book['available_copies']) - 1) # Decrement available copies
    
    save_data()

    # Prepare response
    response_record = new_record.copy()
    response_record['id'] = int(response_record['id'])
    response_record['student_id'] = int(response_record['student_id'])
    response_record['book_id'] = int(response_record['book_id'])

    return jsonify({"message": "Book borrowed successfully", "record": response_record}), 201

@app.route('/reserve/<int:book_id>', methods=['POST'])
@role_required('student')
def reserve_book(book_id):
    """
    Allows a student to reserve a book (Student only).
    """
    student_id_str = request.current_user['id']
    book_id_str = str(book_id)

    book = next((b for b in books_data if b['id'] == book_id_str), None)
    if not book:
        return jsonify({"message": "Book not found"}), 404
    
    # Check if student already has this specific book borrowed or reserved
    existing_record = next((
        rec for rec in borrowing_records_data 
        if rec['student_id'] == student_id_str and rec['book_id'] == book_id_str and rec['status'] in ['borrowed', 'reserved']
    ), None)

    if existing_record:
        return jsonify({"message": "You have already borrowed or reserved this book"}), 400
    
    # Create new reservation record
    new_record_id = _get_next_id(borrowing_records_data)
    new_record = {
        'id': str(new_record_id),
        'student_id': student_id_str,
        'book_id': book_id_str,
        'borrow_date': '', # Empty for reservations
        'due_date': '', # Empty for reservations
        'return_date': '',
        'status': 'reserved'
    }
    borrowing_records_data.append(new_record)
    save_data()

    # Prepare response
    response_record = new_record.copy()
    response_record['id'] = int(response_record['id'])
    response_record['student_id'] = int(response_record['student_id'])
    response_record['book_id'] = int(response_record['book_id'])

    return jsonify({"message": "Book reserved successfully", "record": response_record}), 201

@app.route('/cancel_reservation/<int:borrow_id>', methods=['POST'])
@role_required('student')
def cancel_reservation(borrow_id):
    """
    Allows a student to cancel their own reservation.
    """
    student_id_str = request.current_user['id']
    borrow_id_str = str(borrow_id)

    record = next((
        rec for rec in borrowing_records_data 
        if rec['id'] == borrow_id_str and rec['student_id'] == student_id_str
    ), None)

    if not record:
        return jsonify({"message": "Reservation record not found or does not belong to you"}), 404
    
    if record['status'] != 'reserved':
        return jsonify({"message": "Only reserved books can be cancelled"}), 400
    
    record['status'] = 'cancelled'
    record['return_date'] = datetime.utcnow().isoformat() # Mark cancellation time
    save_data()

    # Prepare response
    response_record = record.copy()
    response_record['id'] = int(response_record['id'])
    response_record['student_id'] = int(response_record['student_id'])
    response_record['book_id'] = int(response_record['book_id'])

    return jsonify({"message": "Reservation cancelled successfully", "record": response_record}), 200


@app.route('/return/<int:borrow_id>', methods=['POST'])
@role_required('librarian')
def return_book(borrow_id):
    """
    Allows a librarian to mark a book as returned (Librarian only).
    """
    borrow_id_str = str(borrow_id)
    record = next((rec for rec in borrowing_records_data if rec['id'] == borrow_id_str), None)

    if not record:
        return jsonify({"message": "Borrowing record not found"}), 404
    
    if record['status'] not in ['borrowed', 'reserved']:
        return jsonify({"message": "Book is not currently borrowed or reserved"}), 400
    
    book = next((b for b in books_data if b['id'] == record['book_id']), None)
    if not book:
        return jsonify({"message": "Associated book not found"}), 500

    record['return_date'] = datetime.utcnow().isoformat()
    record['status'] = 'returned'
    
    # Increment available copies only if it was a borrowed book
    if record['borrow_date']: # Indicates it was borrowed, not just reserved
        book['available_copies'] = str(int(book['available_copies']) + 1)
    
    save_data()

    # Prepare response
    response_record = record.copy()
    response_record['id'] = int(response_record['id'])
    response_record['student_id'] = int(response_record['student_id'])
    response_record['book_id'] = int(response_record['book_id'])

    return jsonify({"message": "Book returned successfully", "record": response_record}), 200

@app.route('/my_books', methods=['GET'])
@role_required('student')
def get_my_books():
    """
    Retrieves all books currently borrowed or reserved by the logged-in student.
    """
    student_id_str = request.current_user['id']
    records = [
        rec for rec in borrowing_records_data 
        if rec['student_id'] == student_id_str and rec['status'] in ['borrowed', 'reserved']
    ]

    result = []
    for record in records:
        book = next((b for b in books_data if b['id'] == record['book_id']), None)
        if book:
            record_data = record.copy()
            record_data['id'] = int(record_data['id'])
            record_data['student_id'] = int(record_data['student_id'])
            record_data['book_id'] = int(record_data['book_id'])
            record_data['book_details'] = {
                'id': int(book['id']),
                'title': book['title'],
                'author': book['author'],
                'isbn': book['isbn'],
                'publication_year': int(book['publication_year']) if book['publication_year'] else None,
                'available_copies': int(book['available_copies']),
                'total_copies': int(book['total_copies'])
            }
            result.append(record_data)
    
    return jsonify(result), 200

@app.route('/borrowed_books', methods=['GET'])
@role_required('librarian')
def get_all_borrowed_books():
    """
    Retrieves all currently borrowed or reserved books (Librarian only).
    """
    records = [
        rec for rec in borrowing_records_data 
        if rec['status'] in ['borrowed', 'reserved']
    ]

    result = []
    for record in records:
        book = next((b for b in books_data if b['id'] == record['book_id']), None)
        student = next((u for u in users_data if u['id'] == record['student_id']), None)
        if book and student:
            record_data = record.copy()
            record_data['id'] = int(record_data['id'])
            record_data['student_id'] = int(record_data['student_id'])
            record_data['book_id'] = int(record_data['book_id'])
            record_data['book_details'] = {
                'id': int(book['id']),
                'title': book['title'],
                'author': book['author'],
                'isbn': book['isbn'],
                'publication_year': int(book['publication_year']) if book['publication_year'] else None,
                'available_copies': int(book['available_copies']),
                'total_copies': int(book['total_copies'])
            }
            record_data['student_details'] = {
                'id': int(student['id']),
                'username': student['username'],
                'role': student['role']
            }
            result.append(record_data)
    
    return jsonify(result), 200

# --- Application Startup ---
# Removed @app.before_first_request as it's deprecated.
# Data initialization will now happen directly when the app module is loaded.
def initialize_app_data(): # Renamed function for clarity
    """Initializes data from CSVs when the app starts."""
    load_data()
    # Ensure CSV files exist with headers if they are newly created
    if not os.path.exists(USERS_CSV) or os.path.getsize(USERS_CSV) == 0:
        _write_csv(USERS_CSV, [], ['id', 'username', 'password_hash', 'role', 'token']) # Added 'token'
    if not os.path.exists(BOOKS_CSV) or os.path.getsize(BOOKS_CSV) == 0:
        _write_csv(BOOKS_CSV, [], ['id', 'title', 'author', 'isbn', 'publication_year', 'available_copies', 'total_copies'])
    if not os.path.exists(BORROWING_RECORDS_CSV) or os.path.getsize(BORROWING_RECORDS_CSV) == 0:
        _write_csv(BORROWING_RECORDS_CSV, [], ['id', 'student_id', 'book_id', 'borrow_date', 'due_date', 'return_date', 'status'])
    print("CSV files initialized if new.")

# Call the initialization function directly after app creation
initialize_app_data()
