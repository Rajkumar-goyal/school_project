from flask_login import UserMixin
from models import User

class LoginUser(UserMixin):
    def __init__(self, user_id, username, role, name):
        self.id = user_id
        self.username = username
        self.role = role
        self.name = name
    
    @staticmethod
    def get(user_id):
        user = User.get_by_id(user_id)
        if user:
            return LoginUser(user.id, user.username, user.role, user.name)
        return None