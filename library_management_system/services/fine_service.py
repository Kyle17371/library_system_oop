from database import connect
def pay_fine(fine_id, user_id):
    with connect() as db:
        fine = db.execute("""SELECT f.* FROM fines f JOIN borrow_transactions t ON t.id=f.transaction_id
                             WHERE f.id=? AND t.user_id=? AND f.status='unpaid'""", (fine_id,user_id)).fetchone()
        if not fine: raise ValueError("Unpaid fine not found.")
        db.execute("INSERT INTO payments(fine_id,amount,received_by,notes) VALUES(?,?,?,?)",
                   (fine_id,fine["amount"],user_id,"Recorded as paid in academic demo"))
        db.execute("UPDATE fines SET status='paid' WHERE id=?", (fine_id,))
        db.commit()
