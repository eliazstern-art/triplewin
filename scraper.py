import requests
import json
import time
from supabase import create_client

# --- הגדרות ---
SUPABASE_URL = "https://webajdmgrbuhwiatgyjq.supabase.co"
SUPABASE_KEY = "sb_publishable_4_NGPFu5qip2Jrb3GrIjuw_nOEmn_U3"

HEADERS = {
    "accept": "*/*",
    "accept-language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
    "content-type": "application/json",
    "origin": "https://headstart.co.il",
    "referer": "https://headstart.co.il/",
    "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
}

HASH_SEGMENTS = "b0a0e327afa087315b0972e4e8aabe03012a8a9ba08a3966674d803a7288a64c"
HASH_REWARDS  = "f962bcac128d515709041ec617a7e343aa1975975c3350f2c43cf23ab118e651"

def make_session():
    session = requests.Session()
    session.get("https://headstart.co.il/", headers=HEADERS, timeout=15)
    time.sleep(1)
    return session

def get_projects(session):
    params = {
        "operationName": "segmentsQuery",
        "variables": json.dumps({
            "axis": 1, "currentLanguage": 1, "defaultLanguage": 1,
            "nearlyFundedListFirst": 50, "popularProjectsListFirst": 50,
            "newProjectsListFirst": 50, "successfulProjectsListFirst": 1,
            "isRandom": False, "onlyCompletelyFunded": "false"
        }, separators=(',', ':')),
        "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": HASH_SEGMENTS}})
    }
    r = session.get("https://headstart.co.il/graphql", params=params, headers=HEADERS, timeout=15)
    print(f"segmentsQuery status: {r.status_code}, length: {len(r.text)}")
    data = r.json()

    projects = []
    seen = set()
    for section in ["nearlyFundedProjects", "popularProjects", "newProjects"]:
        for edge in data["data"][section]["edges"]:
            node = edge["node"]
            if node["projectStatus"] == "active" and node["projectId"] not in seen:
                seen.add(node["projectId"])
                projects.append({
                    "id": node["projectId"],
                    "rowId": node["projectRowId"],
                    "title": node["title"],
                    "funded": node["totalFunded"],
                    "target": node["target"],
                    "deadline": node["targetDate"]
                })
    return projects

def get_rewards(session, project_row_id):
    variables = {
        "first": 1000000,
        "project": project_row_id,
        "projectRewardContents": {"language": 1},
        "projectRewardContentsDefault": {"language": 1},
        "projectRewardShippingMethods": {"language": 1}
    }
    params = {
        "operationName": "projectReward",
        "variables": json.dumps(variables, separators=(',', ':')),
        "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": HASH_REWARDS}})
    }
    r = session.get("https://headstart.co.il/graphql", params=params, headers=HEADERS, timeout=15)
    return r.json()

def main():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("שולף פרויקטים פעילים...")
    session = make_session()
    projects = get_projects(session)
    print(f"נמצאו {len(projects)} פרויקטים")

    for p in projects:
        supabase.table("projects").upsert({
            "id": p["id"],
            "row_id": p["rowId"],
            "title": p["title"],
            "url": f"https://headstart.co.il/project/{p['id']}"
        }).execute()
    print(f"✓ עודכנו {len(projects)} פרויקטים ב-Supabase")

    all_rewards = []
    for p in projects:
        result = get_rewards(session, p["rowId"])
        edges = result.get("data", {}).get("allProjectRewards", {}).get("edges", [])
        for edge in edges:
            r = edge["node"]
            nodes = r.get("rewardContent", {}).get("nodes", [])
            title = nodes[0].get("title", "") if nodes else ""
            quantity = r.get("quantity", 0) or 0
            total_bought = r.get("totalBought", 0) or 0
            available = (quantity == 0) or (total_bought < quantity)
            if available:
                all_rewards.append({
                    "project_id": p["id"],
                    "title": title,
                    "price": float(r.get("price") or 0),
                    "quantity": quantity,
                    "total_bought": total_bought,
                    "available": True,
                    "url": f"https://headstart.co.il/project/{p['id']}"
                })
        print(f"✓ {p['title']} — {len(edges)} תשורות")
        time.sleep(0.3)

    supabase.table("rewards").delete().neq("id", 0).execute()
    for r in all_rewards:
        supabase.table("rewards").upsert(r).execute()

    print(f"\n✅ סה\"כ {len(all_rewards)} תשורות זמינות עודכנו ב-Supabase")

if __name__ == "__main__":
    main()
