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

    # Valid login for bonz with new password
    r_good_login = client.post("/api/auth/login", json={"username": "bonz", "password": "NoStress123!"})
    assert r_good_login.status_code == 200
    auth_resp = r_good_login.json()
    token = auth_resp["token"]
    assert auth_resp["user"]["username"] == "bonz"
    assert auth_resp["user"]["role"] == "superadmin"
    print(f"[PASS] Successfully logged in as bonz [role: {auth_resp['user']['role']}]")

    # Valid login for admin with new password
    r_admin_login = client.post("/api/auth/login", json={"username": "admin", "password": "NoStress123!"})
    assert r_admin_login.status_code == 200
    admin_resp = r_admin_login.json()
    assert admin_resp["user"]["username"] == "admin"
    assert admin_resp["user"]["role"] == "superadmin"
    print("[PASS] Successfully logged in as admin with NoStress123!")

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
    assert "admin" in users_list
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

    # Superadmin resets password for secondary admin
    r_reset_admin = client.post("/api/admin/users/leaddev/reset-password", json={"new_password": "NewDevPass456!"}, headers=auth_headers)
    assert r_reset_admin.status_code == 200
    print("[PASS] Superadmin successfully reset password for 'leaddev'")

    # Test login with newly reset password
    r_lead_login = client.post("/api/auth/login", json={"username": "leaddev", "password": "NewDevPass456!"})
    assert r_lead_login.status_code == 200
    lead_token = r_lead_login.json()["token"]
    lead_headers = {"Authorization": f"Bearer {lead_token}"}
    print("[PASS] Secondary admin 'leaddev' can log in with reset password")

    # Secondary admin CANNOT add other admins (only superadmin bonz can)
    r_forbidden_add = client.post("/api/admin/users", json={"username": "attacker", "password": "123"}, headers=lead_headers)
    assert r_forbidden_add.status_code == 403
    print("[PASS] Secondary admin cannot add other admins (403 Forbidden)")

    # Public/Whitelisted IP Password Reset Endpoint
    r_reset_public = client.post("/api/auth/reset-password", json={"username": "leaddev", "new_password": "AnotherDevPass789!"})
    assert r_reset_public.status_code == 200
    r_lead_login2 = client.post("/api/auth/login", json={"username": "leaddev", "password": "AnotherDevPass789!"})
    assert r_lead_login2.status_code == 200
    print("[PASS] Whitelisted client successfully reset password via /api/auth/reset-password")

    # Delete secondary admin
    r_del_admin = client.delete("/api/admin/users/leaddev", headers=auth_headers)
    assert r_del_admin.status_code == 200
    print("[PASS] Superadmin bonz successfully deleted secondary admin 'leaddev'")

    # Primary owner bonz and admin cannot be deleted
    r_del_bonz = client.delete("/api/admin/users/bonz", headers=auth_headers)
    assert r_del_bonz.status_code == 400
    r_del_admin_super = client.delete("/api/admin/users/admin", headers=auth_headers)
    assert r_del_admin_super.status_code == 400
    print("[PASS] Deletion of primary accounts 'bonz' and 'admin' safely prevented (400 Bad Request)")

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
