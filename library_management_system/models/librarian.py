from .user import LibraryUser
class Librarian(LibraryUser):
    def borrowing_limit(self):
        return 0
    def role_name(self):
        return "librarian"
    def can_request_borrowing(self):
        return False
