"""
飞书 Wiki 信息自动发现脚本
用法：
  py -3 _setup_wiki.py                         # 自动列出空间（需应用已加入知识库）
  py -3 _setup_wiki.py <wiki_url_or_space_id>  # 直接指定 space_id 或粘贴 wiki 页面 URL
"""
import re
import sys
import yaml
import requests

CONFIG_PATH = "config.yaml"
FEISHU_BASE = "https://open.feishu.cn/open-apis"


def get_token(app_id, app_secret):
    r = requests.post(
        f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=15,
    )
    data = r.json()
    if data.get("code", -1) != 0:
        raise RuntimeError(f"Auth failed: {data}")
    return data["tenant_access_token"]


def list_spaces(token):
    r = requests.get(
        f"{FEISHU_BASE}/wiki/v2/spaces",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    return r.json().get("data", {}).get("items", [])


def get_space_info(token, space_id):
    r = requests.get(
        f"{FEISHU_BASE}/wiki/v2/spaces/{space_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    return r.json()


def list_nodes(token, space_id, parent_node_token=None):
    params = {"page_size": 50}
    if parent_node_token:
        params["parent_node_token"] = parent_node_token
    r = requests.get(
        f"{FEISHU_BASE}/wiki/v2/spaces/{space_id}/nodes",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=15,
    )
    data = r.json()
    if data.get("code", -1) != 0:
        return []
    return data.get("data", {}).get("items", [])


def extract_space_id(raw: str):
    """从 URL 或字符串中提取 space_id。"""
    for pat in [r"/wiki/space/([A-Za-z0-9]+)", r"/wiki/([A-Za-z0-9]{10,})"]:
        m = re.search(pat, raw)
        if m:
            return m.group(1)
    # 纯 space_id 字符串
    if re.match(r"^[A-Za-z0-9]{8,}$", raw.strip()):
        return raw.strip()
    return None


def print_nodes(nodes, indent=0):
    for n in nodes:
        has = "+" if n.get("has_child") else " "
        typ = n.get("obj_type", "")
        title = n.get("title", "(无标题)")
        token = n.get("node_token", "")
        print(f"{'  ' * indent}{has}[{typ:6}] {title[:45]:45}  {token}")


def find_best_parent(token, space_id, nodes):
    """按关键词自动选父节点，找不到时返回第一个节点。"""
    keywords = ["论文", "paper", "日报", "daily", "文献", "每日"]
    all_nodes = list(nodes)
    for n in nodes:
        if n.get("has_child"):
            all_nodes += list_nodes(token, space_id, n["node_token"])
    for kw in keywords:
        for n in all_nodes:
            if kw.lower() in n.get("title", "").lower():
                return n
    return all_nodes[0] if all_nodes else None


def write_config(space_id, parent_token):
    with open(CONFIG_PATH, encoding="utf-8") as f:
        raw = f.read()
    for old, new in [
        ('wiki_space_id: ""',    f'wiki_space_id: "{space_id}"'),
        ("wiki_space_id: ''",    f"wiki_space_id: '{space_id}'"),
        ('wiki_parent_node: ""', f'wiki_parent_node: "{parent_token}"'),
        ("wiki_parent_node: ''", f"wiki_parent_node: '{parent_token}'"),
    ]:
        raw = raw.replace(old, new)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(raw)


def main():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    app_id     = cfg["feishu"]["app_id"]
    app_secret = cfg["feishu"]["app_secret"]

    print("Step 1: Get tenant_access_token")
    token = get_token(app_id, app_secret)
    print(f"  OK\n")

    # ── 确定 space_id ─────────────────────────────────────
    space_id = None
    if len(sys.argv) > 1:
        space_id = extract_space_id(sys.argv[1])
        print(f"Step 2: Using provided space_id = {space_id}\n")
    else:
        print("Step 2: Auto-discovering wiki spaces ...")
        spaces = list_spaces(token)
        if spaces:
            space_id = spaces[0]["space_id"]
            print(f"  Found: {spaces[0].get('name','')} (space_id={space_id})\n")
        else:
            print("  No spaces found (app not added as collaborator yet).")
            print()
            print("  Please either:")
            print("  A) Add the app as a wiki collaborator in Feishu, then rerun this script")
            print("  B) Run:  py -3 _setup_wiki.py <your_wiki_page_url>")
            print("     e.g.: py -3 _setup_wiki.py https://xxx.feishu.cn/wiki/SomeLongID")
            print()
            print("  How to get wiki URL:")
            print("  Open your wiki space in browser, copy the URL from address bar.")
            print("  The space_id is the long alphanumeric string after /wiki/")
            sys.exit(0)

    # ── 验证 space_id ─────────────────────────────────────
    print("Step 3: Verify space access ...")
    info = get_space_info(token, space_id)
    if info.get("code", -1) != 0:
        print(f"  FAILED: code={info.get('code')} msg={info.get('msg')}")
        print()
        print("  Solution: In Feishu wiki settings, add this app as a space member:")
        print(f"    App ID: {app_id}")
        print("  Steps: Wiki homepage -> top-right gear -> Members -> Add -> search app name")
        sys.exit(1)
    space_name = info.get("data", {}).get("space", {}).get("name", "")
    print(f"  OK: '{space_name}'\n")

    # ── 列出节点树 ────────────────────────────────────────
    print("Step 4: List wiki nodes ...")
    nodes = list_nodes(token, space_id)
    if nodes:
        print_nodes(nodes)
        print()
        for n in nodes:
            if n.get("has_child"):
                children = list_nodes(token, space_id, n["node_token"])
                if children:
                    print(f"  >> {n.get('title','?')}/")
                    print_nodes(children, indent=1)
    else:
        print("  (empty space)")

    # ── 选取父节点 ────────────────────────────────────────
    print()
    if nodes:
        target = find_best_parent(token, space_id, nodes)
    else:
        target = None

    if target:
        parent_token = target["node_token"]
        parent_name  = target.get("title", "")
        print(f"Step 5: Auto-selected parent node: [{parent_name}]  token={parent_token}")
    else:
        parent_token = ""
        parent_name  = "(root)"
        print("Step 5: Using root as parent (no nodes found)")

    # ── 写入 config ───────────────────────────────────────
    print()
    print("Step 6: Writing to config.yaml ...")
    write_config(space_id, parent_token)
    print(f"  wiki_space_id    = {space_id}")
    print(f"  wiki_parent_node = {parent_token}  ({parent_name})")
    print()
    print("Done! Wiki config updated.")


if __name__ == "__main__":
    main()
