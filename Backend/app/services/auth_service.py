from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, DuplicateError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.users = UserRepository(db)

    async def register(self, payload: RegisterRequest) -> User:
        existing = await self.users.get_by_email(payload.email)
        if existing:
            raise DuplicateError("An account with this email already exists", "EMAIL_ALREADY_REGISTERED")

        user = User(
            name=payload.name,
            email=payload.email.lower(),
            password_hash=hash_password(payload.password),
            role=UserRole.USER,
            is_active=True,
        )
        return await self.users.create(user)

    async def login(self, payload: LoginRequest) -> TokenResponse:
        user = await self.users.get_by_email(payload.email.lower())
        if not user or not verify_password(payload.password, user.password_hash):
            raise AuthenticationError("Invalid email or password", "INVALID_CREDENTIALS")
        if not user.is_active:
            raise AuthenticationError("Account is disabled", "ACCOUNT_DISABLED")

        token = create_access_token(subject=user.id, role=user.role.value)
        return TokenResponse(access_token=token)
