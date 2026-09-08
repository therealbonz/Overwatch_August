import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starlette.testclient import TestClient
from backend.main import app
from backend.auth import init_auth_data

def run_auth_tests():
    init_auth_data()
    client = TestClient(app)

    print("\n--- 1. Testing Guest Access (Public vs Locked) ---")
    # Public endpoints
    r_repos = client.get("/api/repos")
    assert r_repos.status_code == 200, f"Guest repos status: {r_repos.status_code}"
    print("[PASS] Guest can view GitHub repos")

    r_projects = client.get("/api/cms/projects")
    assert r_projects.status_code == 200
    print("[PASS] Guest can view launchpad projects")

    # Locked endpoints for guest
    r_create_repo = client.post("/api/repos/create", json={"name": "test"})
    assert r_create_repo.status_code == 401, f"Expected 401, got {r_create_repo.status_code}"
    print("[PASS] Guest blocked from creating GitHub repo (401)")

    r_folders = client.get("/api/server/folders")
    assert r_folders.status_code == 401
    print("[PASS] Guest blocked from viewing server folders (401)")

    r_create_folder = client.post("/api/server/folders/create", json={"folder_name": "test"})
    assert r_create_folder.status_code == 401
    print("[PASS] Guest blocked from creating server folders (401)")

    r_create_cms = client.post("/api/cms/projects", json={"title": "Test", "url": "https://example.com"})
    assert r_create_cms.status_code == 401
    print("[PASS] Guest blocked from adding CMS project (401)")

    print("\n--- 2. Testing Admin Login ---")
    # Invalid password
    r_bad_login = client.post("/api/auth/login", json={"username": "bonz", "password": "wrongpassword"})
    assert r_bad_login.status_code == 401
    print("[PASS] Invalid password rejected (401)")

    # Valid login for bonz
    r_good_login = client.post("/api/auth/login", json={"username": "bonz", "password": "bonzadmin2026"})
    assert r_good_login.status_code == 200
    auth_resp = r_good_login.json()
    token = auth_resp["token"]
    assert auth_resp["user"]["username"] == "bonz"
    assert auth_resp["user"]["role"] == "superadmin"
    print(f"[PASS] Successfully logged in as bonz [role: {auth_resp['user']['role']}]")

    auth_headers = {"Authorization": f"Bearer {token}"}

    print("\n--- 3. Testing Authenticated Admin Endpoints ---")
    # Server folders accessible now
    r_auth_folders = client.get("/api/server/folders", headers=auth_headers)
    assert r_auth_folders.status_code == 200
    print(f"[PASS] Authenticated admin can inspect server folders ({len(r_auth_folders.json()['items'])} items)")

    # Superadmin admin management
    r_users = client.get("/api/admin/users", headers=auth_headers)
    assert r_users.status_code == 200
    users_list = [u["username"] for u in r_users.json()["users"]]
    assert "bonz" in users_list
    print(f"[PASS] Superadmin can list admins: {users_list}")

    # Add secondary admin
    new_admin = {
        "username": "leaddev",
        "display_name": "Lead Developer",
        "password": "devpassword123",
        "role": "admin"
    }
    r_add_admin = client.post("/api/admin/users", json=new_admin, headers=auth_headers)
    assert r_add_admin.status_code == 200
    print("[PASS] Superadmin bonz successfully added secondary admin 'leaddev'")

    # Test login as secondary admin
    r_lead_login = client.post("/api/auth/login", json={"username": "leaddev", "password": "devpassword123"})
    assert r_lead_login.status_code == 200
    lead_token = r_lead_login.json()["token"]
    lead_headers = {"Authorization": f"Bearer {lead_token}"}
    print("[PASS] Secondary admin 'leaddev' can log in successfully")

    # Secondary admin CANNOT add other admins (only superadmin bonz can)
    r_forbidden_add = client.post("/api/admin/users", json={"username": "attacker", "password": "123"}, headers=lead_headers)
    assert r_forbidden_add.status_code == 403
    print("[PASS] Secondary admin cannot add other admins (403 Forbidden)")

    # Delete secondary admin
    r_del_admin = client.delete("/api/admin/users/leaddev", headers=auth_headers)
    assert r_del_admin.status_code == 200
    print("[PASS] Superadmin bonz successfully deleted secondary admin 'leaddev'")

    # Primary owner bonz cannot be deleted
    r_del_owner = client.delete("/api/admin/users/bonz", headers=auth_headers)
    assert r_del_owner.status_code == 400
    print("[PASS] Deletion of primary owner 'bonz' safely prevented (400 Bad Request)")

    print("\n--- 4. Testing IP Whitelist Security Settings ---")
    r_sec = client.get("/api/admin/security", headers=auth_headers)
    assert r_sec.status_code == 200
    sec_data = r_sec.json()
    assert "68.146.118.91" in sec_data["trusted_ips"]
    print(f"[PASS] IP Whitelist contains owner IP: {sec_data['trusted_ips']}")

    # Add trusted IP
    r_add_ip = client.post("/api/admin/security/trusted-ips", json={"ip_pattern": "192.168.1.*"}, headers=auth_headers)
    assert r_add_ip.status_code == 200
    assert "192.168.1.*" in r_add_ip.json()["trusted_ips"]
    print("[PASS] Added new IP pattern to whitelist")

    # Remove trusted IP
    r_del_ip = client.delete("/api/admin/security/trusted-ips/192.168.1.*", headers=auth_headers)
    assert r_del_ip.status_code == 200
    assert "192.168.1.*" not in r_del_ip.json()["trusted_ips"]
    print("[PASS] Removed IP pattern from whitelist")

    print("\n=======================================================")
    print(" ALL AUTH & SECURITY TESTS PASSED SUCCESSFULLY! ")
    print("=======================================================")

if __name__ == "__main__":
    run_auth_tests()
