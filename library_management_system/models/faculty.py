from .user import LibraryUser
class Faculty(LibraryUser):
    def borrowing_limit(self):
        return 5
    def role_name(self):
        return "faculty"
