from database import connect
def dashboard_counts(user_id=None):
    with connect() as db:
        if user_id is None:
            return {
                "books": db.execute("SELECT COUNT(*) FROM books").fetchone()[0],
                "copies": db.execute("SELECT COUNT(*) FROM book_copies").fetchone()[0],
                "borrowed": db.execute("SELECT COUNT(*) FROM borrow_transactions WHERE status IN ('borrowed','overdue')").fetchone()[0],
                "pending": db.execute("SELECT COUNT(*) FROM borrow_transactions WHERE status='pending'").fetchone()[0],
                "overdue": db.execute("SELECT COUNT(*) FROM borrow_transactions WHERE status='overdue' OR (status='borrowed' AND due_date < date('now'))").fetchone()[0],
                "users": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            }
        return {
            "active": db.execute("SELECT COUNT(*) FROM borrow_transactions WHERE user_id=? AND status IN ('borrowed','overdue','pending')", (user_id,)).fetchone()[0],
            "history": db.execute("SELECT COUNT(*) FROM borrow_transactions WHERE user_id=? AND status='returned'", (user_id,)).fetchone()[0],
            "fines": db.execute("SELECT COALESCE(SUM(f.amount),0) FROM fines f JOIN borrow_transactions t ON t.id=f.transaction_id WHERE t.user_id=? AND f.status='unpaid'", (user_id,)).fetchone()[0],
        }
