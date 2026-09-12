# django secret key generator
import secrets

SECRET_KEY = secrets.token_urlsafe(50)
print(SECRET_KEY)
