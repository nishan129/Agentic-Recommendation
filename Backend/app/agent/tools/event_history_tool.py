"""
Event History Tool — gives the agent a digest of what the user has
actually done, in a shape cheap to feed into an LLM prompt (not raw ORM
objects, not the full event table).
"""
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.event_repository import EventRepository
from app.repositories.product_repository import ProductRepository


@dataclass
class EventDigestItem:
    event_type: str
    product_title: str | None
    category: str | None
    search_query: str | None
    timestamp: str


@dataclass
class EventDigest:
    items: list[EventDigestItem] = field(default_factory=list)
    category_counts: dict[str, int] = field(default_factory=dict)
    search_terms: list[str] = field(default_factory=list)
    seen_product_ids: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return len(self.items) == 0

    def to_prompt_text(self, max_items: int = 40) -> str:
        """Render as compact text for an LLM prompt — newest first,
        capped so the prompt doesn't grow unbounded for power users."""
        lines = []
        for item in self.items[:max_items]:
            parts = [item.event_type]
            if item.product_title:
                parts.append(f'product="{item.product_title}"')
            if item.category:
                parts.append(f"category={item.category}")
            if item.search_query:
                parts.append(f'query="{item.search_query}"')
            lines.append(" | ".join(parts))
        return "\n".join(lines) if lines else "(no activity yet)"


async def get_event_digest(db: AsyncSession, user_id: str, limit: int = 200) -> EventDigest:
    """Fetch and summarize a user's recent events for the agent's
    reasoning step."""
    events = EventRepository(db)
    products = ProductRepository(db)

    recent = await events.get_recent_for_user(user_id, limit=limit)

    digest = EventDigest()
    category_counter: Counter[str] = Counter()
    search_terms: list[str] = []
    seen_ids: set[str] = set()

    # Cache product lookups within this call — many events share products.
    product_cache: dict[str, object] = {}

    for event in recent:
        product_title = None
        category = None
        if event.product_id:
            seen_ids.add(event.product_id)
            if event.product_id not in product_cache:
                product_cache[event.product_id] = await products.get_by_id(event.product_id)
            product = product_cache[event.product_id]
            if product:
                product_title = product.title
                category = product.category
                category_counter[product.category] += 1

        if event.search_query:
            search_terms.append(event.search_query)

        digest.items.append(
            EventDigestItem(
                event_type=event.event_type,
                product_title=product_title,
                category=category,
                search_query=event.search_query,
                timestamp=event.timestamp.isoformat(),
            )
        )

    digest.category_counts = dict(category_counter)
    digest.search_terms = search_terms
    digest.seen_product_ids = list(seen_ids)
    return digest
