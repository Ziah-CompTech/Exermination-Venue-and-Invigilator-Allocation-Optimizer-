# Demonstration Script
## Examination Venue and Invigilator Allocation Optimiser

**Duration:** ~12 minutes  
**Audience:** Lecturer / examiner  
**Prerequisites:** Server running (`python run.py`), MySQL up, browser open to `http://127.0.0.1:5000`.

---

## Act 1 — The problem (1 min, no screen)

*Say this while the login page is showing:*

> Educational institutions schedule hundreds of exams per cycle. Doing this
> manually produces the problems we're solving here:
>
> - Overcrowded rooms
> - Double-booked venues
> - Invigilators supervising their own subjects
> - Unfair staff workloads
> - Last-minute clashes discovered too late
>
> This system automates the whole allocation using a **constraint solver**
> called CP-SAT from Google OR-Tools. It doesn't just assign rooms
> greedily — it proves the schedule is valid against institutional rules.

---

## Act 2 — Log in as the examination officer (30 sec)

**Action:**
- Username: `officer`
- Password: `Password123!`
- Click **Sign in**.

**Point out:**
- The dashboard shows summary cards: students, examinations, venues, invigilators.
- The top menu shows: Dashboard, Subjects, Examinations, Venues, Invigilators, Allocations, Reports.
- **Users** and **Settings** are missing — those are admin-only.
- This is **role-based access control**, enforced server-side.

---

## Act 3 — Show the master data (2 min)

**Action:** Click **Subjects** in the menu.

**Point out:**
- Subjects and departments already seeded.
- Click **Venues**: 6 venues with different types (exam hall, lab, seminar room) and capacities, one under maintenance.

**Action:** Click **Invigilators**.

**Point out:**
- Five staff. Two have **subjects taught** listed.
- "Dr. Alice Kamau teaches CS101 and CS201."
- **This is the conflict-of-interest source.** The solver will never assign her
  to invigilate a CS101 exam, because she teaches it.
- Open her profile → click **Availability** → shows an entry. Staff availability
  is enforced by the solver.
- Click **Workload** → shows daily and period caps.

**Action:** Click **Examinations**.

**Point out:**
- Six examinations ready for allocation.
- Different venue-type requirements: some need `exam_hall`, some need
  `projector` facilities, one is large (180 candidates).

**Action:** Click the CS101 exam → **Manage Sessions**.

**Point out:**
- The session is the actual date/time/candidate count.
- Click **New Examination** just to show the form, then back out.

---

## Act 4 — Run the optimiser (2 min)

**Action:** Click **Allocations** in the menu → **New Allocation Run**.

**Action:** In the form:
- Exam period: `2025-S1`
- Leave dates blank
- Max time: `30`
- Leave "Allow under-capacity" unchecked

**Say this before clicking:**

> The solver is about to look at every session and every venue and find a
> valid assignment. It respects:
>
> - Venue capacity and facilities
> - Non-overlap for venues in time
> - Non-overlap for invigilators in time
> - Subject-teaching exclusion
> - Availability windows
> - Daily and period workload caps
>
> If no valid solution exists, it will tell us honestly rather than produce
> a broken schedule.

**Action:** Click **Run Optimiser**.  
**Observation:** Spinner appears, then the run result page.

**Point out:**
- Status: **`optimal`** (green badge) — the best possible assignment.
- Wall time: under a second.
- The result table shows every session with its assigned venue(s) and invigilator(s).
- Note: the CS101 exam was assigned to a **venue with `projector`** — matching
  the exam's required facilities.
- Note: Dr. Kamau is **not** on the CS101 panel, because she teaches that subject.

---

## Act 5 — Conflict viewer (1 min)

**Action:** Click **Allocations → Conflict Viewer**.

**Point out:**
- All sections say `None.` — the schedule is clean.
- This is a live scan of the database, not a cached report.

---

## Act 6 — Approve and publish (1 min)

**Action:** Click back to the run → **Approve** → **Publish**.

**Point out:**
- The run now shows **Approved** and **Published** badges.
- Publishing triggered notifications to affected invigilators. *(If you have
  a second browser or incognito window, log in as `inv_dr_kamau` and show the
  bell.)*
- Publishing is **validated again** — the system re-runs the conflict check
  before allowing publication. You cannot publish a broken schedule.

---

## Act 7 — Reports (2 min)

**Action:** Click **Reports** in the menu.

**Point out:**
- Eight reports, all reading live data.

**Action:** Click **Master Timetable** → toolbar shows CSV / PDF / Print.

**Action:** Click **PDF**.

**Point out:** The downloaded PDF has the institution header, the generated
timestamp, and the full timetable with venues and invigilators.

**Action:** Go back → **Venue Utilisation** → shows a bar chart of how much
each venue is being used.

**Action:** Go back → **Staff Workload** → shows duty counts per invigilator.

**Action:** Go back → **Conflict & Exception Report** → all sections show
counts, and empty ones say "None."

---

## Act 8 — Proving the constraints work (2 min)

**This is the strongest part of the demo.** It proves the solver is not
"just assigning rooms."

### Act 8a — Force an impossible schedule

**Action:**
1. Go to **Examinations** → find the CS101 exam.
2. Click **Edit**.
3. Change **Registered candidates** to `9999`.
4. Save.

**Action:** Go to **Allocations → New Allocation Run** → period `2025-S1` →
**Run Optimiser**.

**Point out:**
- Status: **`infeasible`** (red badge).
- Diagnostics section reads something like:
  *"Session 1 (CS101): eligible venue capacity 320 < candidates 9999."*

**Say:**
> The solver proved that no valid schedule exists, and it told us exactly
> why. It didn't invent a bad schedule. It didn't silently seat half the
> students. It reported the truth.

### Act 8b — Fix and re-run

**Action:**
1. Go back to the CS101 exam → **Edit** → change candidates back to `25`.
2. Save.
3. **Allocations → New Allocation Run** → period `2025-S1` → **Run Optimiser**.

**Point out:** Status returns to **`optimal`**. The schedule is valid again.

---

## Act 9 — Conflict-of-interest demo (1.5 min)

**Action:**
1. Go to **Examinations** → create a new examination:
   - Title: `CS101 Supplementary`
   - Subject: `CS101 — Introduction to Programming`
   - Period: `2025-S1`
   - Candidates: `5`
   - Invigilators required: `1`
   - Status: `Scheduled`
2. Save. Click **Manage Sessions** → add a session on any future date, `09:00`–`10:30`, 5 candidates.

**Action:** Now go to **Invigilators** and make sure **all neutral invigilators** are... actually skip this step; the demo works if there are at least two eligible.

**Action:** **Allocations → New Allocation Run** → `2025-S1` → **Run Optimiser**.

**Point out:**
- On the result, the CS101 Supplementary session was assigned an invigilator
  who does **not** teach CS101.
- Dr. Kamau (who teaches CS101) is deliberately excluded.
- This is a **hard constraint** — no amount of re-running the solver will
  assign her.

---

## Act 10 — Student view (1 min)

**Action:** Open a new incognito / private window → `http://127.0.0.1:5000` → log in as `stu_001` / `Password123!`.

**Point out:**
- Landed directly on **"My Examination Timetable"** — the student's personal view.
- The table shows only *their* exams with dates, times, venues.
- Try typing `http://127.0.0.1:5000/users/` — lands on **403 Access denied**.
  That's the role gate working server-side; you can't bypass it by URL.

**Action:** Log out of the student session.

---

## Act 11 — Admin view (30 sec)

**Action:** Log in as `admin` / `Password123!`.

**Action:** Click **Users** → shows all accounts, roles, status.

**Action:** Click **Audit Log** (top-right of Users page).

**Point out:**
- Every action from the entire demo is recorded: logins, subject edits,
  allocation runs, approvals, publications.
- Each entry shows the user, action, entity, timestamp, and IP.
- Audit entries are append-only — ordinary users cannot edit or delete them.

---

## Closing (30 sec)

**Say:**
> To summarise: the system enforces every institutional rule as a **hard
> constraint** in a CP-SAT model, so it cannot produce an invalid schedule.
> When a valid schedule doesn't exist, it says so honestly and tells you why.
> When one does exist, it optimises for fairness and efficient venue use.
>
> Everything you've seen is real data in MySQL, real OR-Tools solving, and
> real reports. Nothing is hardcoded.

---

## Q&A preparation

Anticipate these questions:

**Q: What if the solver takes too long?**  
A: The time limit is configurable per run. If the solver hits it, it returns
   `feasible` (a valid but not provably optimal solution) or `unknown` if it
   can't establish one — it never claims success it can't prove.

**Q: How does the conflict-of-interest rule work?**  
A: Lecturers are linked to subjects in an `invigilator_subjects` table. The
   solver treats this as an eligibility pre-filter — a lecturer who teaches a
   subject is simply not in the candidate pool for that subject's exams.

**Q: Can invigilators be swapped manually?**  
A: Yes — manual editing is planned with per-action revalidation. For now,
   you re-run the optimiser after adjusting data.

**Q: Is the password secure?**  
A: Passwords are hashed with Werkzeug (PBKDF2-SHA256 with per-user salts).
   Failed logins are throttled; the account locks after 5 attempts.

**Q: What if two exams overlap for the same student?**  
A: The system has a student-subject-registration table and detects student
   collisions, showing them in the Conflict Viewer. Preventing them by
   design would require scheduling students individually — a next step.

**Q: Why not just use Excel?**  
A: Excel cannot enforce fifteen simultaneous constraints, and cannot prove
   that a schedule is valid. This system can.

---

## Timing summary

| Act | Topic | Time |
|---|---|---|
| 1 | Problem statement | 1 min |
| 2 | Officer login + RBAC | 0.5 min |
| 3 | Master data tour | 2 min |
| 4 | Run optimiser | 2 min |
| 5 | Conflict viewer | 1 min |
| 6 | Approve + publish | 1 min |
| 7 | Reports + PDF | 2 min |
| 8 | Infeasibility + fix | 2 min |
| 9 | Conflict-of-interest | 1.5 min |
| 10 | Student view + 403 | 1 min |
| 11 | Admin + audit log | 0.5 min |
| — | Closing | 0.5 min |
| **Total** | | **~15 min** |

---

## Pre-demo checklist

Before you sit down in front of the lecturer, verify:

- [ ] MySQL is running
- [ ] `python run.py` is running without errors
- [ ] You are logged out (start from the login page)
- [ ] Demo passwords are `Password123!` for all demo accounts
- [ ] At least one user exists for each of: admin, officer, invigilator, student
- [ ] At least 3 subjects, 3 venues, 2 invigilators, and 4 sessions exist
- [ ] Browser is on `http://127.0.0.1:5000/login`
- [ ] DevTools is closed (it clutters the demo)
- [ ] Report downloads folder is empty or clearly visible so downloads land there
- [ ] You've rehearsed Act 8 (the infeasible → fix cycle) at least once