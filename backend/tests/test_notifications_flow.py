from sqlalchemy import select

from app.models.notification import Notification, NotificationType
from app.models.user import AccountStatus, User


def create_user(db_session, email: str) -> User:
    user = User(
        full_name=email.split('@')[0],
        email=email,
        password_hash='test-hash',
        preferred_language='ru',
        account_status=AccountStatus.ACTIVE,
        roles=[],
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def create_notification(
    db_session,
    *,
    user_id: int,
    is_read: bool,
    title: str = 'Notification',
) -> Notification:
    notification = Notification(
        user_id=user_id,
        notification_type=NotificationType.NEW_MESSAGE,
        title=title,
        body='Test body',
        is_read=is_read,
    )
    db_session.add(notification)
    db_session.commit()
    db_session.refresh(notification)
    return notification


def test_mark_all_notifications_read_marks_only_current_user(
    client,
    db_session,
    set_current_user,
):
    owner = create_user(db_session, 'notif-owner@example.com')
    other = create_user(db_session, 'notif-other@example.com')

    create_notification(db_session, user_id=owner.id, is_read=False, title='u1-1')
    create_notification(db_session, user_id=owner.id, is_read=False, title='u1-2')
    create_notification(db_session, user_id=owner.id, is_read=True, title='u1-3')
    other_unread = create_notification(
        db_session,
        user_id=other.id,
        is_read=False,
        title='u2-1',
    )

    set_current_user(owner)

    response = client.post('/api/v1/notifications/read-all')

    assert response.status_code == 200
    assert response.json()['marked_count'] == 2

    owner_unread_count = db_session.scalar(
        select(Notification)
        .where(Notification.user_id == owner.id, Notification.is_read.is_(False))
    )
    assert owner_unread_count is None

    db_session.refresh(other_unread)
    assert other_unread.is_read is False


def test_delete_notification_deletes_only_owned_item(client, db_session, set_current_user):
    owner = create_user(db_session, 'notif-delete-owner@example.com')
    other = create_user(db_session, 'notif-delete-other@example.com')

    own_notification = create_notification(
        db_session,
        user_id=owner.id,
        is_read=False,
        title='own',
    )
    foreign_notification = create_notification(
        db_session,
        user_id=other.id,
        is_read=False,
        title='foreign',
    )

    set_current_user(owner)

    own_delete_response = client.delete(f'/api/v1/notifications/{own_notification.id}')
    assert own_delete_response.status_code == 204

    deleted_own = db_session.scalar(
        select(Notification).where(Notification.id == own_notification.id)
    )
    assert deleted_own is None

    foreign_delete_response = client.delete(
        f'/api/v1/notifications/{foreign_notification.id}'
    )
    assert foreign_delete_response.status_code == 404

    still_exists = db_session.scalar(
        select(Notification).where(Notification.id == foreign_notification.id)
    )
    assert still_exists is not None


def test_delete_all_notifications_removes_all_for_current_user(
    client,
    db_session,
    set_current_user,
):
    owner = create_user(db_session, 'notif-clear-owner@example.com')
    other = create_user(db_session, 'notif-clear-other@example.com')

    create_notification(db_session, user_id=owner.id, is_read=False, title='o1')
    create_notification(db_session, user_id=owner.id, is_read=True, title='o2')
    create_notification(db_session, user_id=other.id, is_read=False, title='x1')

    set_current_user(owner)

    response = client.delete('/api/v1/notifications')

    assert response.status_code == 200
    assert response.json()['deleted_count'] == 2

    owner_items = db_session.scalars(
        select(Notification).where(Notification.user_id == owner.id)
    ).all()
    assert owner_items == []

    other_items = db_session.scalars(
        select(Notification).where(Notification.user_id == other.id)
    ).all()
    assert len(other_items) == 1
