import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "instance" / "library.db"

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 username TEXT NOT NULL UNIQUE,
 password_hash TEXT NOT NULL,
 full_name TEXT NOT NULL,
 email TEXT NOT NULL UNIQUE,
 role TEXT NOT NULL CHECK(role IN ('librarian','student','faculty')),
 student_number TEXT,
 department TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS categories (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS authors (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS books (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 isbn TEXT UNIQUE,
 title TEXT NOT NULL,
 publisher TEXT,
 publication_year INTEGER,
 category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
 description TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS book_authors (
 book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
 author_id INTEGER NOT NULL REFERENCES authors(id) ON DELETE CASCADE,
 PRIMARY KEY(book_id, author_id)
);
CREATE TABLE IF NOT EXISTS book_copies (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
 accession_number TEXT NOT NULL UNIQUE,
 status TEXT NOT NULL DEFAULT 'available'
   CHECK(status IN ('available','requested','borrowed','reserved','maintenance')),
 shelf_location TEXT
);
CREATE TABLE IF NOT EXISTS borrow_transactions (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER NOT NULL REFERENCES users(id),
 copy_id INTEGER NOT NULL REFERENCES book_copies(id),
 request_date TEXT NOT NULL DEFAULT CURRENT_DATE,
 borrow_date TEXT,
 due_date TEXT,
 return_date TEXT,
 status TEXT NOT NULL DEFAULT 'pending'
   CHECK(status IN ('pending','borrowed','returned','rejected','overdue')),
 approved_by INTEGER REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS reservations (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER NOT NULL REFERENCES users(id),
 book_id INTEGER NOT NULL REFERENCES books(id),
 reservation_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 status TEXT NOT NULL DEFAULT 'waiting'
   CHECK(status IN ('waiting','fulfilled','cancelled'))
);
CREATE TABLE IF NOT EXISTS fines (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 transaction_id INTEGER NOT NULL UNIQUE REFERENCES borrow_transactions(id),
 amount REAL NOT NULL DEFAULT 0 CHECK(amount >= 0),
 status TEXT NOT NULL DEFAULT 'unpaid' CHECK(status IN ('unpaid','paid'))
);
CREATE TABLE IF NOT EXISTS payments (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 fine_id INTEGER NOT NULL REFERENCES fines(id),
 amount REAL NOT NULL CHECK(amount > 0),
 payment_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 received_by INTEGER REFERENCES users(id),
 notes TEXT
);
CREATE TABLE IF NOT EXISTS library_settings (
 setting_key TEXT PRIMARY KEY,
 setting_value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS activity_logs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER REFERENCES users(id),
 action TEXT NOT NULL,
 details TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_books_title ON books(title);
CREATE INDEX IF NOT EXISTS idx_copies_status ON book_copies(status);
CREATE INDEX IF NOT EXISTS idx_borrow_user ON borrow_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_borrow_status_due ON borrow_transactions(status, due_date);
CREATE INDEX IF NOT EXISTS idx_reservation_queue ON reservations(book_id, status, reservation_date);
"""

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with connect() as db:
        db.executescript(SCHEMA)
        db.execute("INSERT OR IGNORE INTO library_settings VALUES ('fine_per_day','5')")
        db.execute("INSERT OR IGNORE INTO library_settings VALUES ('loan_days','14')")
        users = [
            ("admin", "Librarian Admin", "admin@university.edu", "librarian", None, "Library"),
            ("student1", "Alex Student", "student1@university.edu", "student", "2026-0001", "Computer Studies"),
            ("faculty1", "Jordan Faculty", "faculty1@university.edu", "faculty", None, "Computer Studies"),
        ]
        for username, name, email, role, number, dept in users:
            db.execute("""INSERT OR IGNORE INTO users
                (username,password_hash,full_name,email,role,student_number,department)
                VALUES (?,?,?,?,?,?,?)""",
                (username, generate_password_hash("password123"), name, email, role, number, dept))
        if db.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 0:
            cats = ["Information Technology", "Science", "Literature", "Mathematics"]
            for c in cats: db.execute("INSERT INTO categories(name) VALUES (?)", (c,))
            samples = [
                ("978013", "Python Programming: An Introduction", "Academic Press", 2023, "Information Technology", "A practical introduction to programming."),
                ("978026", "Introduction to Algorithms", "MIT Press", 2022, "Information Technology", "Core algorithms and problem-solving."),
                ("978000", "The Art of Science", "University Press", 2021, "Science", "An overview of scientific thinking."),
            ]
            for isbn, title, publisher, year, category, desc in samples:
                cid = db.execute("SELECT id FROM categories WHERE name=?", (category,)).fetchone()["id"]
                cur = db.execute("INSERT INTO books(isbn,title,publisher,publication_year,category_id,description) VALUES(?,?,?,?,?,?)",
                                 (isbn,title,publisher,year,cid,desc))
                bid = cur.lastrowid
                aid = db.execute("INSERT INTO authors(name) VALUES (?)", ("University Library Editorial Team",)).lastrowid if not db.execute("SELECT id FROM authors WHERE name=?", ("University Library Editorial Team",)).fetchone() else db.execute("SELECT id FROM authors WHERE name=?", ("University Library Editorial Team",)).fetchone()["id"]
                db.execute("INSERT INTO book_authors VALUES (?,?)", (bid, aid))
                for n in range(1, 3):
                    db.execute("INSERT INTO book_copies(book_id,accession_number,shelf_location) VALUES(?,?,?)",
                               (bid, f"LIB-{bid:03d}-{n:02d}", f"棚 A-{bid}"))
        db.commit()
