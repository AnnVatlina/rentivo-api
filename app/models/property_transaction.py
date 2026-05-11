import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PropertyTransaction(Base):
    __tablename__ = "property_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)       # income | expense
    category: Mapped[str] = mapped_column(String(50), nullable=False)   # mortgage|utilities|tax|maintenance|rent|other
    title: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    billing_cycle: Mapped[str] = mapped_column(String(20), nullable=False)  # one_time|weekly|monthly|quarterly|yearly
    transaction_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # for one_time
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)        # for recurring
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
