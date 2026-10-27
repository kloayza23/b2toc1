from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import hash_password
from .models import User


def seed_demo_user(
    db: Session,
    *,
    username: str,
    email: str,
    name: str,
    password: str,
) -> User:
    """Create or refresh the explicitly configured local demo account."""
    normalized_username = username.strip().lower()
    normalized_email = email.strip().lower()
    user = db.scalar(select(User).where(User.username == normalized_username))
    if user is None:
        user = User(
            username=normalized_username,
            email=normalized_email,
            name=name.strip(),
            password_hash=hash_password(password),
        )
        db.add(user)
    else:
        user.email = normalized_email
        user.name = name.strip()
        user.password_hash = hash_password(password)
    db.commit()
    db.refresh(user)
    return user
