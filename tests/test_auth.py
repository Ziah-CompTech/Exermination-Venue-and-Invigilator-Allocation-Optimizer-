def test_login_requires_credentials(client):
    r = client.post("/login", data={}, follow_redirects=True)
    assert b"Invalid" in r.data or b"required" in r.data.lower()


def test_login_success_and_logout(client, admin, login):
    r = login("admin_test")
    assert b"Dashboard" in r.data
    r = client.get("/logout", follow_redirects=True)
    assert b"Sign in" in r.data or b"Welcome" not in r.data


def test_role_gate_blocks_student_from_users(client, app, login):
    from app.extensions import db
    from app.models.user import User
    with app.app_context():
        u = User.query.filter_by(username="stu_gate").first()
        if not u:
            u = User(username="stu_gate",
                     email="stu_gate@test.local",
                     full_name="Stu Gate", role="student",
                     is_active=True)
            u.set_password("Passw0rd!")
            db.session.add(u)
            db.session.commit()
    login("stu_gate")
    r = client.get("/users/")
    assert r.status_code == 403


def test_password_change(client, admin, login):
    login("admin_test")
    r = client.post("/change-password", data={
        "current_password": "Passw0rd!",
        "new_password": "NewPassw0rd!",
        "confirm": "NewPassw0rd!",
    }, follow_redirects=True)
    assert b"updated" in r.data.lower()
    client.post("/change-password", data={
        "current_password": "NewPassw0rd!",
        "new_password": "Passw0rd!",
        "confirm": "Passw0rd!",
    }, follow_redirects=True)


def test_login_throttling(client, app):
    from app.extensions import db
    from app.models.user import User
    with app.app_context():
        u = User.query.filter_by(username="lockme").first()
        if not u:
            u = User(username="lockme", email="lockme@test.local",
                     full_name="Lock Me", role="student", is_active=True)
            u.set_password("RightPass!")
            db.session.add(u)
            db.session.commit()
    for _ in range(6):
        client.post("/login",
                    data={"username": "lockme", "password": "wrong"},
                    follow_redirects=True)
    with app.app_context():
        u = User.query.filter_by(username="lockme").first()
        assert u.locked_until is not None