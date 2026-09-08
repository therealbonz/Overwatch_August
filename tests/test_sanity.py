import sys
from starlette.testclient import TestClient
from backend.main import app

def run_tests():
    client = TestClient(app)

    # 1. Test Static files
    r1 = client.get("/")
    assert r1.status_code == 200, f"Root status: {r1.status_code}"
    assert "therealbonz.com" in r1.text, "Homepage title missing"
    assert "3D Cube Interactive Studio" in r1.text, "3D Cube section missing"
    print("[PASS] Static index.html and assets served correctly")

    # 2. Test system status
    r2 = client.get("/api/system/status")
    assert r2.status_code == 200, f"Status API: {r2.status_code}"
    data2 = r2.json()
    assert data2["status"] == "healthy"
    print(f"[PASS] System status API: {data2['domain']}, user: {data2['github']['user']}, authenticated: {data2['github']['authenticated']}")

    # 3. Test CMS projects
    r3 = client.get("/api/cms/projects")
    assert r3.status_code == 200
    projects = r3.json()["projects"]
    assert len(projects) >= 4, f"Expected >= 4 projects, got {len(projects)}"
    titles = [p["title"] for p in projects]
    assert "3D Cube Project" in titles
    assert "JsProject" in titles
    assert "Bonz2D Game" in titles
    print(f"[PASS] CMS projects API returned {len(projects)} projects: {titles}")

    # 4. Test Server folders API
    r4 = client.get("/api/server/folders")
    assert r4.status_code == 200
    folders = r4.json()
    assert "items" in folders
    print(f"[PASS] Server folders API base: {folders['base_dir']}, items count: {len(folders['items'])}")

    # 5. Test Repos API
    r5 = client.get("/api/repos")
    assert r5.status_code == 200
    repos_data = r5.json()
    repo_names = [r["name"] for r in repos_data["repos"]]
    print(f"[PASS] GitHub repos API returned {repos_data['count']} repositories: {repo_names}")

    # 6. Test CMS Project Add and Delete
    new_proj = {
        "title": "Test Launch Project",
        "category": "Testing",
        "url": "https://example.com",
        "priority": 99
    }
    r_add = client.post("/api/cms/projects", json=new_proj)
    assert r_add.status_code == 200, f"Add project failed: {r_add.text}"
    created_id = r_add.json()["project"]["id"]
    print(f"[PASS] CMS project created with id: {created_id}")

    r_del = client.delete(f"/api/cms/projects/{created_id}")
    assert r_del.status_code == 200, f"Delete project failed: {r_del.text}"
    print(f"[PASS] CMS project deleted cleanly")

    print("\n=======================================================")
    print(" ALL 6 VERIFICATION TEST SUITES PASSED SUCCESSFULLY! ")
    print("=======================================================")

if __name__ == "__main__":
    run_tests()
