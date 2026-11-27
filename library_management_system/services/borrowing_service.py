from datetime import date, timedelta
from database import connect
from models import Student, Faculty, Librarian

def user_from_row(row):
    cls = {"student": Student, "faculty": Faculty, "librarian": Librarian}[row["role"]]
    return cls(row["id"], row["username"], row["full_name"], row["email"], row["department"])

def request_borrow(user_id, copy_id):
    with connect() as db:
        user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not user or user["role"] == "librarian": raise ValueError("Only students and faculty can request borrowing.")
        policy = user_from_row(user)
        active = db.execute("SELECT COUNT(*) FROM borrow_transactions WHERE user_id=? AND status IN ('pending','borrowed','overdue')", (user_id,)).fetchone()[0]
        if active >= policy.borrowing_limit(): raise ValueError(f"Borrowing limit reached ({policy.borrowing_limit()}).")
        copy = db.execute("SELECT * FROM book_copies WHERE id=?", (copy_id,)).fetchone()
        if not copy or copy["status"] != "available": raise ValueError("This copy is not currently available.")
        cur = db.execute("INSERT INTO borrow_transactions(user_id,copy_id) VALUES(?,?)", (user_id,copy_id))
        db.execute("UPDATE book_copies SET status='requested' WHERE id=?", (copy_id,))
        db.commit()
        return cur.lastrowid

def approve_borrow(transaction_id, librarian_id):
    with connect() as db:
        tx = db.execute("SELECT * FROM borrow_transactions WHERE id=?", (transaction_id,)).fetchone()
        if not tx or tx["status"] != "pending": raise ValueError("Request is no longer pending.")
        days = int(db.execute("SELECT setting_value FROM library_settings WHERE setting_key='loan_days'").fetchone()[0])
        today = date.today()
        db.execute("UPDATE borrow_transactions SET status='borrowed',borrow_date=?,due_date=?,approved_by=? WHERE id=?",
                   (today.isoformat(), (today+timedelta(days=days)).isoformat(), librarian_id, transaction_id))
        db.execute("UPDATE book_copies SET status='borrowed' WHERE id=?", (tx["copy_id"],))
        db.commit()

def reject_borrow(transaction_id):
    with connect() as db:
        tx = db.execute("SELECT * FROM borrow_transactions WHERE id=?", (transaction_id,)).fetchone()
        if not tx or tx["status"] != "pending": raise ValueError("Request is no longer pending.")
        db.execute("UPDATE borrow_transactions SET status='rejected' WHERE id=?", (transaction_id,))
        db.execute("UPDATE book_copies SET status='available' WHERE id=?", (tx["copy_id"],))
        db.commit()

def process_return(transaction_id):
    with connect() as db:
        tx = db.execute("SELECT * FROM borrow_transactions WHERE id=?", (transaction_id,)).fetchone()
        if not tx or tx["status"] not in ("borrowed","overdue"): raise ValueError("This transaction cannot be returned.")
        today = date.today()
        amount = 0.0
        if tx["due_date"] and today > date.fromisoformat(tx["due_date"]):
            rate = float(db.execute("SELECT setting_value FROM library_settings WHERE setting_key='fine_per_day'").fetchone()[0])
            amount = (today-date.fromisoformat(tx["due_date"])).days * rate
        db.execute("UPDATE borrow_transactions SET status='returned',return_date=? WHERE id=?", (today.isoformat(),transaction_id))
        db.execute("UPDATE book_copies SET status='available' WHERE id=?", (tx["copy_id"],))
        if amount > 0:
            db.execute("INSERT OR REPLACE INTO fines(transaction_id,amount,status) VALUES(?,?,'unpaid')", (transaction_id,amount))
        db.commit()
        return amount
