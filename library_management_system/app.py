from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import check_password_hash
from database import init_db, connect
from services.borrowing_service import request_borrow, approve_borrow, reject_borrow, process_return
from services.reservation_service import reserve_book
from services.fine_service import pay_fine
from services.report_service import dashboard_counts

app = Flask(__name__)
app.secret_key = "replace-this-development-secret-before-deployment"
init_db()

def current_user():
    if "user_id" not in session: return None
    with connect() as db:
        return db.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def roles(*allowed):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            user = current_user()
            if user["role"] not in allowed: abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def log(action, details=""):
    with connect() as db:
        db.execute("INSERT INTO activity_logs(user_id,action,details) VALUES(?,?,?)",
                   (session.get("user_id"), action, details))
        db.commit()

@app.context_processor
def inject_user():
    return {"logged_user": current_user()}

@app.route("/")
def index():
    return redirect(url_for("dashboard")) if current_user() else redirect(url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username, password = request.form.get("username","").strip(), request.form.get("password","")
        with connect() as db:
            user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            log("LOGIN", f"{user['username']} logged in")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("auth/login.html")

@app.route("/logout")
@login_required
def logout():
    log("LOGOUT", "User logged out")
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    if user["role"] == "librarian":
        stats = dashboard_counts()
        with connect() as db:
            pending = db.execute("""SELECT t.*,u.full_name,b.title,c.accession_number FROM borrow_transactions t
                JOIN users u ON u.id=t.user_id JOIN book_copies c ON c.id=t.copy_id
                JOIN books b ON b.id=c.book_id WHERE t.status='pending' ORDER BY t.request_date""").fetchall()
            recent = db.execute("SELECT * FROM activity_logs ORDER BY id DESC LIMIT 8").fetchall()
        return render_template("admin/dashboard.html", stats=stats, pending=pending, recent=recent)
    stats = dashboard_counts(user["id"])
    with connect() as db:
        active = db.execute("""SELECT t.*,b.title,c.accession_number FROM borrow_transactions t
            JOIN book_copies c ON c.id=t.copy_id JOIN books b ON b.id=c.book_id
            WHERE t.user_id=? AND t.status IN ('pending','borrowed','overdue') ORDER BY t.id DESC""", (user["id"],)).fetchall()
    return render_template("user/dashboard.html", stats=stats, active=active)

@app.route("/catalog")
@login_required
def catalog():
    q = request.args.get("q","").strip()
    with connect() as db:
        books = db.execute("""SELECT b.*,cat.name category,
            (SELECT COUNT(*) FROM book_copies c WHERE c.book_id=b.id AND c.status='available') available,
            (SELECT GROUP_CONCAT(a.name, ', ') FROM book_authors ba JOIN authors a ON a.id=ba.author_id WHERE ba.book_id=b.id) authors
            FROM books b LEFT JOIN categories cat ON cat.id=b.category_id
            WHERE b.title LIKE ? OR COALESCE(b.isbn,'') LIKE ? OR COALESCE(cat.name,'') LIKE ?
            ORDER BY b.title""", (f"%{q}%",f"%{q}%",f"%{q}%")).fetchall()
    with connect() as db:
        copies = {b["id"]: db.execute("SELECT id,accession_number FROM book_copies WHERE book_id=? AND status='available' ORDER BY accession_number", (b["id"],)).fetchall() for b in books}
    return render_template("catalog.html", books=books, q=q, copies=copies)

@app.route("/books/add", methods=["GET","POST"])
@roles("librarian")
def add_book():
    with connect() as db:
        categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()
    if request.method == "POST":
        title = request.form.get("title","").strip()
        accession = request.form.get("accession","").strip()
        if not title or not accession:
            flash("Title and first copy accession number are required.", "danger")
            return render_template("admin/book_form.html", categories=categories)
        try:
            with connect() as db:
                cat = request.form.get("category_id") or None
                cur = db.execute("INSERT INTO books(isbn,title,publisher,publication_year,category_id,description) VALUES(?,?,?,?,?,?)",
                    (request.form.get("isbn") or None,title,request.form.get("publisher"),request.form.get("year") or None,cat,request.form.get("description")))
                bid = cur.lastrowid
                author_name = request.form.get("author","").strip()
                if author_name:
                    row = db.execute("SELECT id FROM authors WHERE name=?", (author_name,)).fetchone()
                    aid = row["id"] if row else db.execute("INSERT INTO authors(name) VALUES(?)", (author_name,)).lastrowid
                    db.execute("INSERT INTO book_authors VALUES(?,?)", (bid,aid))
                db.execute("INSERT INTO book_copies(book_id,accession_number,shelf_location) VALUES(?,?,?)",
                           (bid,accession,request.form.get("shelf_location")))
                extra = int(request.form.get("extra_copies") or 0)
                for i in range(extra):
                    db.execute("INSERT INTO book_copies(book_id,accession_number,shelf_location) VALUES(?,?,?)",
                               (bid,f"{accession}-{i+2}",request.form.get("shelf_location")))
                db.commit()
            log("BOOK_ADDED", title)
            flash("Book and physical copy saved.", "success")
            return redirect(url_for("catalog"))
        except Exception as e:
            flash(f"Could not save book: {e}", "danger")
    return render_template("admin/book_form.html", categories=categories)

@app.route("/borrow/<int:copy_id>", methods=["POST"])
@roles("student","faculty")
def borrow(copy_id):
    try:
        request_borrow(session["user_id"], copy_id)
        log("BORROW_REQUEST", f"Copy ID {copy_id}")
        flash("Borrow request submitted. Wait for librarian approval.", "success")
    except Exception as e: flash(str(e), "danger")
    return redirect(url_for("catalog"))

@app.route("/reserve/<int:book_id>", methods=["POST"])
@roles("student","faculty")
def reserve(book_id):
    try:
        reserve_book(session["user_id"], book_id)
        log("RESERVATION", f"Book ID {book_id}")
        flash("Reservation added to the waiting queue.", "success")
    except Exception as e: flash(str(e), "danger")
    return redirect(url_for("catalog"))

@app.route("/requests/<int:tx_id>/<action>", methods=["POST"])
@roles("librarian")
def handle_request(tx_id, action):
    try:
        if action == "approve": approve_borrow(tx_id, session["user_id"])
        elif action == "reject": reject_borrow(tx_id)
        else: abort(404)
        log("BORROW_"+action.upper(), f"Transaction {tx_id}")
        flash(f"Request {action}d.", "success")
    except Exception as e: flash(str(e), "danger")
    return redirect(url_for("dashboard"))

@app.route("/returns")
@roles("librarian")
def returns():
    with connect() as db:
        rows = db.execute("""SELECT t.*,u.full_name,b.title,c.accession_number FROM borrow_transactions t
          JOIN users u ON u.id=t.user_id JOIN book_copies c ON c.id=t.copy_id JOIN books b ON b.id=c.book_id
          WHERE t.status IN ('borrowed','overdue') ORDER BY t.due_date""").fetchall()
    return render_template("admin/returns.html", rows=rows)

@app.route("/returns/<int:tx_id>", methods=["POST"])
@roles("librarian")
def do_return(tx_id):
    try:
        fine = process_return(tx_id)
        log("BOOK_RETURNED", f"Transaction {tx_id}; fine={fine:.2f}")
        flash(f"Return processed. Fine: ₱{fine:.2f}", "success")
    except Exception as e: flash(str(e), "danger")
    return redirect(url_for("returns"))

@app.route("/history")
@login_required
def history():
    user = current_user()
    with connect() as db:
        if user["role"] == "librarian":
            rows = db.execute("""SELECT t.*,u.full_name,b.title,c.accession_number FROM borrow_transactions t
              JOIN users u ON u.id=t.user_id JOIN book_copies c ON c.id=t.copy_id JOIN books b ON b.id=c.book_id
              ORDER BY t.id DESC""").fetchall()
        else:
            rows = db.execute("""SELECT t.*,u.full_name,b.title,c.accession_number FROM borrow_transactions t
              JOIN users u ON u.id=t.user_id JOIN book_copies c ON c.id=t.copy_id JOIN books b ON b.id=c.book_id
              WHERE t.user_id=? ORDER BY t.id DESC""", (user["id"],)).fetchall()
    return render_template("history.html", rows=rows)

@app.route("/fines")
@login_required
def fines():
    user = current_user()
    with connect() as db:
        sql = """SELECT f.*,t.user_id,b.title FROM fines f JOIN borrow_transactions t ON t.id=f.transaction_id
                 JOIN book_copies c ON c.id=t.copy_id JOIN books b ON b.id=c.book_id"""
        rows = db.execute(sql + ("" if user["role"]=="librarian" else " WHERE t.user_id=?") + " ORDER BY f.id DESC",
                           () if user["role"]=="librarian" else (user["id"],)).fetchall()
    return render_template("fines.html", rows=rows)

@app.route("/fines/<int:fine_id>/pay", methods=["POST"])
@roles("student","faculty")
def pay(fine_id):
    try:
        pay_fine(fine_id, session["user_id"])
        flash("Payment marked as paid in this academic demo.", "success")
    except Exception as e: flash(str(e), "danger")
    return redirect(url_for("fines"))

@app.route("/reports")
@roles("librarian")
def reports():
    stats = dashboard_counts()
    with connect() as db:
        popular = db.execute("""SELECT b.title,COUNT(t.id) total FROM books b
          JOIN book_copies c ON c.book_id=b.id JOIN borrow_transactions t ON t.copy_id=c.id
          GROUP BY b.id ORDER BY total DESC LIMIT 10""").fetchall()
        logs = db.execute("""SELECT l.*,u.full_name FROM activity_logs l LEFT JOIN users u ON u.id=l.user_id
          ORDER BY l.id DESC LIMIT 30""").fetchall()
    return render_template("admin/reports.html", stats=stats, popular=popular, logs=logs)

@app.route("/settings", methods=["GET","POST"])
@roles("librarian")
def settings():
    with connect() as db:
        if request.method == "POST":
            days = max(1, min(60, int(request.form.get("loan_days",14))))
            fine = max(0, float(request.form.get("fine_per_day",5)))
            db.execute("UPDATE library_settings SET setting_value=? WHERE setting_key='loan_days'", (str(days),))
            db.execute("UPDATE library_settings SET setting_value=? WHERE setting_key='fine_per_day'", (str(fine),))
            db.commit()
            flash("Library policies updated.", "success")
        vals = {r["setting_key"]:r["setting_value"] for r in db.execute("SELECT * FROM library_settings")}
    return render_template("admin/settings.html", vals=vals)

@app.errorhandler(403)
def forbidden(e): return render_template("error.html", code=403, message="You do not have permission to access this page."), 403
@app.errorhandler(404)
def not_found(e): return render_template("error.html", code=404, message="The page or record was not found."), 404

if __name__ == "__main__":
    app.run(debug=True)
