def test_officer_cannot_manage_users(client, officer, login):
    login("officer_test")
    assert client.get("/users/").status_code == 403
    assert client.get("/settings/").status_code == 403


def test_unauthenticated_redirected(client):
    r = client.get("/students/")
    assert r.status_code in (302, 401)
    if r.status_code == 302:
        assert "/login" in r.headers["Location"]


def test_student_cannot_view_officer_reports(client, app, login):
    from app.extensions import db
    from app.models.user import User
    with app.app_context():
        u = User.query.filter_by(username="stu_rep").first()
        if not u:
            u = User(username="stu_rep", email="stu_rep@test.local",
                     full_name="Stu Rep", role="student",
                     is_active=True)
            u.set_password("Passw0rd!")
            db.session.add(u)
            db.session.commit()
    login("stu_rep")
    assert client.get("/reports/master-timetable").status_code == 403