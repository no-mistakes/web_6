from datetime import datetime
from app.app import app
from app.models import db, User, Category

with app.app_context():
    # --- обычные пользователи ---
    for i in range(1, 11):
        u = User(
            login=f"user{i}",
            first_name=f"Иван{i}",
            last_name=f"Иванов{i}",
            middle_name=f"Иваныч{i}",
        )
        u.set_password("pass123")
        db.session.add(u)

    # --- преподаватели (такие же пользователи, просто логин другой) ---
    for i in range(1, 11):
        t = User(
            login=f"teacher{i}",
            first_name=f"Петр{i}",
            last_name=f"Петров{i}",
            middle_name=f"Петрович{i}",
        )
        t.set_password("teach123")
        db.session.add(t)

    # --- категории ---
    for name in ["Экономика", "Языкознание", "История", "Спорт", "Математика", "Программирование"]:
        db.session.add(Category(name=name))

    db.session.commit()
    print("Добавлено 10 users, 10 teachers, 6 категорий")
