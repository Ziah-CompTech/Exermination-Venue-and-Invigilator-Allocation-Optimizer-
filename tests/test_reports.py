def test_master_timetable_csv_export(app, client, officer, login):
    login("officer_test")
    r = client.get("/reports/master-timetable?format=csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers["Content-Type"]


def test_venue_utilisation_pdf(app, client, officer, login):
    login("officer_test")
    r = client.get("/reports/venue-utilisation?format=pdf")
    assert r.status_code == 200
    assert r.data.startswith(b"%PDF")


def test_unallocated_report_renders(app, client, officer, login):
    login("officer_test")
    r = client.get("/reports/unallocated")
    assert r.status_code == 200
    assert b"Unallocated" in r.data