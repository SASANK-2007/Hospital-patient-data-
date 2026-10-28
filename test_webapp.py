"""End-to-end test for the Flask web site."""
import urllib.request
import urllib.error
import http.cookiejar
import urllib.parse
import re

cj = http.cookiejar.CookieJar()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


opener = urllib.request.build_opener(NoRedirect, urllib.request.HTTPCookieProcessor(cj))


def req(url, data=None, method=None):
    if data is not None:
        data = urllib.parse.urlencode(data).encode()
    r = urllib.request.Request(url, data=data, method=method)
    try:
        resp = opener.open(r, timeout=15)
        return resp.status, resp.read().decode("utf-8", "ignore"), resp.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore"), e.headers


BASE = "http://127.0.0.1:5000"
results = []


def check(label, cond):
    results.append((label, bool(cond)))
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}")


print("=== AUTH ===")
s, b, h = req(BASE + "/")
check("Unauthenticated / redirects to login (302)", s == 302 and "login" in (h.get("Location") or ""))
s, b, h = req(BASE + "/login")
check("Login page renders", s == 200 and "Sign in" in b)
s, b, h = req(BASE + "/login", {"username": "wrong", "password": "x"})
check("Bad credentials rejected", "Invalid username" in b)
s, b, h = req(BASE + "/login", {"username": "admin", "password": "admin123"})
check("Good credentials redirect (302)", s == 302)

print("\n=== PAGES ===")
for path, marker in [
    ("/", "Total Visits"),
    ("/patients", "Patient Records"),
    ("/departments", "Departments"),
    ("/visits", "Recorded Visits"),
    ("/reports", "Department-wise Workload"),
]:
    s, b, h = req(BASE + path)
    check(f"GET {path} renders ({marker})", s == 200 and marker in b)

print("\n=== FILTERS ===")
s, b, h = req(BASE + "/visits?department=1&visit_type=Consultation&date_from=2026-01-01&date_to=2026-12-31")
check("Visits filter applies", s == 200 and "Recorded Visits" in b)
s, b, h = req(BASE + "/reports?date_from=2026-01-01&date_to=2026-06-30")
check("Reports date filter applies", s == 200 and "Days Active" in b)

print("\n=== CSV EXPORTS ===")
for name in ["department_workload", "monthly_visits", "daily_visits",
             "age_band", "visit_type", "gender"]:
    s, b, h = req(BASE + "/export/" + name)
    lines = b.strip().split("\n")
    check(f"export {name}", s == 200 and "OPERATIONAL STATISTICS" in b and len(lines) > 2)

print("\n=== CRUD ===")
# Patient add + delete
req(BASE + "/patients/add", {"age_band": "30-44", "gender": "F"})
s, b, h = req(BASE + "/patients")
m = re.findall(r"patients/(\d+)/delete", b)
pid = m[-1] if m else None
check("Add patient", s == 200 and pid is not None)
if pid:
    s, b, h = req(f"{BASE}/patients/{pid}/delete", {}, method="POST")
    s, b, h = req(BASE + "/patients")
    check("Delete patient", f"patients/{pid}/delete" not in b)

# Visit add + delete
req(BASE + "/visits/add", {"patient_id": "1", "department_id": "1",
                           "visit_date": "2026-10-27", "visit_type": "Consultation"})
s, b, h = req(BASE + "/visits")
m = re.findall(r"visits/(\d+)/delete", b)
vid = m[0] if m else None
check("Add visit", s == 200 and vid is not None)
if vid:
    s, b, h = req(f"{BASE}/visits/{vid}/delete", {}, method="POST")
    check("Delete visit", s == 302)

# Department add + rename + delete
req(BASE + "/departments/add", {"name": "TestWard"})
s, b, h = req(BASE + "/departments")
check("Add department", "TestWard" in b)
# Find the id of the row whose update form contains TestWard
did_test = None
for form in re.findall(r"departments/\d+/update.*?</form>", b, re.S):
    if "TestWard" in form and did_test is None:
        m_id = re.search(r"departments/(\d+)/update", form)
        if m_id:
            did_test = m_id.group(1)
if did_test is None:
    rows = re.findall(r"departments/(\d+)/update", b)
    did_test = rows[-1] if rows else None
if did_test:
    req(f"{BASE}/departments/{did_test}/update", {"name": "TestWard2"}, method="POST")
    s, b, h = req(BASE + "/departments")
    check("Rename department", "TestWard2" in b)
    req(f"{BASE}/departments/{did_test}/delete", {}, method="POST")
    s, b, h = req(BASE + "/departments")
    check("Delete department", "TestWard" not in b and "TestWard2" not in b)
else:
    check("Rename department (id found)", False)
    check("Delete department", False)

print("\n=== LOGOUT ===")
s, b, h = req(BASE + "/logout")
check("Logout redirects (302)", s == 302)
s, b, h = req(BASE + "/")
check("Protected page blocked after logout (302)", s == 302)

passed = sum(1 for _, ok in results if ok)
print(f"\n{'='*50}")
print(f"RESULT: {passed}/{len(results)} checks passed")
print("=" * 50)
raise SystemExit(0 if passed == len(results) else 1)
