class Reservation:
    def __init__(self, reservation_id, user_id, book_id, status="waiting"):
        self.reservation_id = reservation_id
        self.user_id = user_id
        self.book_id = book_id
        self.status = status
