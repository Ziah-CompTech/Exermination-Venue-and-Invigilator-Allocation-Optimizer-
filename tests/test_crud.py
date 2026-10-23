def test_student_unique_registration(app, client, officer, login):
    login("officer_test")
    payload = {"reg_number": "CRUD1", "full_name": "Crud One",
               "email": "", "phone": "", "year_of_study": 1,
               "programme": "", "department_id": 0}
    r = client.post("/students/new", data=payload, follow_redirects=True)
    assert b"created" in r.data.lower() or b"exists" in r.data.lower()
    r2 = client.post("/students/new", data=payload, follow_redirects=True)
    assert b"already exists" in r2.data


def test_venue_capacity_validation(app, client, officer, login):
    login("officer_test")
    r = client.post("/venues/new", data={
        "code": "CAPTEST", "name": "Cap Test",
        "capacity": 10, "usable_capacity": 100,
        "venue_type": "exam_hall", "status": "available",
    }, follow_redirects=True)
    assert b"cannot exceed" in r.data