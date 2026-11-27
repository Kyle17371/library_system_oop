from database import connect
def reserve_book(user_id, book_id):
    with connect() as db:
        exists = db.execute("SELECT id FROM books WHERE id=?", (book_id,)).fetchone()
        if not exists: raise ValueError("Book not found.")
        duplicate = db.execute("SELECT id FROM reservations WHERE user_id=? AND book_id=? AND status='waiting'", (user_id,book_id)).fetchone()
        if duplicate: raise ValueError("You already have a waiting reservation for this book.")
        db.execute("INSERT INTO reservations(user_id,book_id) VALUES(?,?)", (user_id,book_id))
        db.commit()
