from app.db import init_db, session_scope
from app.services.notifications import clear_notification_state, create_subscription, list_subscriptions
from app.schemas import SubscriptionRequest


def test_database_initialization_persists_subscription_records() -> None:
    init_db()
    clear_notification_state()
    created = create_subscription(
        SubscriptionRequest(
            email="persisted@example.com",
            country="Germany",
            topic="photovoltaic",
            frequency="immediate",
            min_impact="medium",
        )
    )

    with session_scope() as session:
        session.expire_all()

    subscriptions = list_subscriptions()
    assert subscriptions[0].id == created.id
    clear_notification_state()
