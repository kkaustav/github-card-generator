# backend/mcp_server.py
from fastmcp import FastMCP
import httpx, json, os
from google import genai as google_genai

mcp = FastMCP("github-card-server")


@mcp.tool()
async def scrape_github(username: str) -> dict:
    """Calls GitHub REST API and returns rich profile + repo data."""
    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(headers=headers, timeout=15) as client:
        profile_resp = await client.get(f"https://api.github.com/users/{username}")
        repos_resp   = await client.get(
            f"https://api.github.com/users/{username}/repos?sort=pushed&per_page=20"
        )

    profile = profile_resp.json()
    repos_raw = repos_resp.json() if isinstance(repos_resp.json(), list) else []

    # Language frequency across all repos
    languages: dict = {}
    for r in repos_raw:
        if r.get("language"):
            languages[r["language"]] = languages.get(r["language"], 0) + 1

    # Top repos by stars, then by recency
    top_repos = sorted(
        [
            {
                "name":        r["name"],
                "stars":       r["stargazers_count"],
                "forks":       r["forks_count"],
                "language":    r.get("language") or "",
                "description": (r.get("description") or "").strip(),
                "url":         r["html_url"],
                "pushed_at":   r.get("pushed_at", ""),
            }
            for r in repos_raw
            if not r.get("fork")          # skip forks
        ],
        key=lambda x: (x["stars"], x["pushed_at"]),
        reverse=True,
    )[:5]

    # Account age in years
    created = profile.get("created_at", "")
    account_age = ""
    if created:
        from datetime import datetime, timezone
        joined = datetime.fromisoformat(created.replace("Z", "+00:00"))
        years = (datetime.now(timezone.utc) - joined).days // 365
        account_age = f"{years} yr" if years else "< 1 yr"

    # Blog / LinkedIn cleanup
    blog = (profile.get("blog") or "").strip()
    if blog and not blog.startswith("http"):
        blog = "https://" + blog

    return {
        "username":      username,
        "name":          profile.get("name") or f"@{username}",
        "bio":           (profile.get("bio") or "").strip(),
        "company":       (profile.get("company") or "").replace("@", "").strip(),
        "location":      profile.get("location") or "",
        "email":         profile.get("email") or "",
        "blog":          blog,
        "twitter":       profile.get("twitter_username") or "",
        "public_repos":  profile.get("public_repos", 0),
        "followers":     profile.get("followers", 0),
        "following":     profile.get("following", 0),
        "account_age":   account_age,
        "top_repos":     top_repos,
        "languages":     languages,
        "avatar_url":    profile.get("avatar_url", f"https://github.com/{username}.png"),
        "profile_url":   f"https://github.com/{username}",
    }


@mcp.tool()
async def analyze_profile(github_data: dict) -> dict:
    """Uses Gemini 2.5 Flash to generate dev personality analysis."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    client = google_genai.Client(api_key=api_key)

    prompt = f"""Analyze this GitHub profile and return a JSON object with exactly these keys:
    - developer_vibe: 1 punchy sentence describing their coding personality (based on bio + repos). Ensure proper capitalization for all technologies (e.g., Machine Learning, AI, Cloud, Python).
    - top_skills: list of 3-5 skills inferred from languages, bio, company AND repo names/descriptions (include SQL if any data/analytics repos exist)
    - fun_fact: 1 clever/witty sentence about something unique in their repos or activity
    - card_theme: one of: hacker, builder, researcher, designer, open-source-hero
    - superpower: 1 short catchy phrase (4 words max) like "Cloud & AI Professional", "Data Developer", or "ML Builder". DO NOT use specific senior titles like "Architect", "Lead", or "Principal" unless explicitly stated in their bio.

    Profile: {json.dumps(github_data)}
    Return ONLY valid JSON, no markdown, no explanation."""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


@mcp.tool()
async def generate_card_html(username: str, github_data: dict, analysis: dict) -> str:
    """Generates a compact, premium dark dev card similar to showcase style."""

    themes = {
        "hacker":           {"grad1": "#0d1117", "grad2": "#1a2332", "accent": "#00ff41", "muted": "#8b949e"},
        "builder":          {"grad1": "#0a0f1e", "grad2": "#0d1f3c", "accent": "#38bdf8", "muted": "#94a3b8"},
        "researcher":       {"grad1": "#0f0e17", "grad2": "#1a1240", "accent": "#a78bfa", "muted": "#a0a0c0"},
        "designer":         {"grad1": "#180011", "grad2": "#2d0030", "accent": "#f472b6", "muted": "#c084fc"},
        "open-source-hero": {"grad1": "#021a0e", "grad2": "#033a1a", "accent": "#4ade80", "muted": "#86efac"},
    }
    t = themes.get(analysis.get("card_theme", "builder"), themes["builder"])
    grad1, grad2, accent, muted = t["grad1"], t["grad2"], t["accent"], t["muted"]

    # Skills badges
    skills_html = " ".join(
        f"<span class='badge'>{s}</span>" for s in analysis.get("top_skills", [])
    )

    # Top repos — compact bullet style like friend's card
    top3 = github_data.get("top_repos", [])[:3]
    repos_html = ""
    for r in top3:
        desc = (r.get("description") or "").strip()
        desc_part = f" — {desc[:55]}{'…' if len(desc)>55 else ''}" if desc else ""
        repos_html += f"<li><b>{r['name']}</b>{desc_part}</li>"

    # Contact line
    info_parts = []
    if github_data.get("location"):   info_parts.append(f"📍 {github_data['location']}")
    if github_data.get("company"):    info_parts.append(f"🏢 {github_data['company']}")
    info_line = " &nbsp;·&nbsp; ".join(info_parts)

    name     = github_data.get("name", f"@{username}")
    vibe     = analysis.get("developer_vibe", "")
    fun      = analysis.get("fun_fact", "")
    superpower = analysis.get("superpower", "")
    repos_count = github_data.get("public_repos", 0)
    followers   = github_data.get("followers", 0)
    following   = github_data.get("following", 0)

    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"/>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet"/>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#080c14;font-family:'Inter',sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:16px}}
.card{{background:linear-gradient(145deg,{grad1},{grad2});border:1px solid {accent}33;border-radius:20px;padding:24px;max-width:400px;width:100%;box-shadow:0 0 40px {accent}1a,0 20px 50px rgba(0,0,0,.7)}}
.top{{display:flex;gap:14px;align-items:center;margin-bottom:16px}}
.avatar{{width:72px;height:72px;border-radius:50%;border:2px solid {accent};flex-shrink:0}}
.name{{font-size:1.2rem;font-weight:800;color:#f0f6fc;line-height:1.2}}
.handle{{font-size:.8rem;color:{muted};margin-top:3px}}
.superpower{{font-size:.72rem;color:{accent};font-weight:700;text-transform:uppercase;letter-spacing:.8px;margin-top:5px}}
.vibe{{font-size:.82rem;color:#c9d1d9;font-style:italic;line-height:1.6;margin-bottom:14px;padding-bottom:14px;border-bottom:1px solid {accent}22}}
.label{{font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:{muted};margin-bottom:7px}}
.badges{{margin-bottom:14px}}
.badge{{display:inline-block;background:{accent}18;color:{accent};border:1px solid {accent}40;border-radius:20px;font-size:.72rem;font-weight:600;padding:3px 11px;margin:2px}}
.stats{{display:flex;gap:8px;margin-bottom:14px}}
.stat{{flex:1;background:#ffffff0a;border:1px solid {accent}22;border-radius:10px;padding:9px 6px;text-align:center}}
.stat-n{{font-size:1.1rem;font-weight:800;color:{accent}}}
.stat-l{{font-size:.62rem;color:{muted};text-transform:uppercase;letter-spacing:.5px;margin-top:1px}}
.repos{{margin-bottom:12px}}
ul{{padding-left:1.1rem;margin:0}}
li{{font-size:.78rem;color:#c9d1d9;margin-bottom:5px;line-height:1.45}}
li b{{color:#f0f6fc;font-weight:600}}
.fun{{background:{accent}0f;border-left:3px solid {accent};border-radius:0 8px 8px 0;padding:8px 12px;font-size:.76rem;color:#c9d1d9;line-height:1.5;margin-bottom:14px}}
.info{{font-size:.72rem;color:{muted};margin-bottom:12px}}
.footer{{display:flex;justify-content:space-between;align-items:center;border-top:1px solid {accent}22;padding-top:12px}}
.gh-link{{font-size:.73rem;color:{accent};text-decoration:none;font-weight:600}}
.gh-link:hover{{text-decoration:underline}}
.watermark{{font-size:.65rem;color:{muted}}}
</style></head><body><div class="card">
  <div class="top">
    <img class="avatar" src="{github_data.get('avatar_url', f'https://github.com/{username}.png')}" crossorigin="anonymous" alt="{username}"/>
    <div>
      <div class="name">{name}</div>
      <div class="handle">@{username}</div>
      {f'<div class="superpower">⚡ {superpower}</div>' if superpower else ''}
    </div>
  </div>
  <div class="vibe">"{vibe}"</div>
  <div class="label">🛠 Skills</div>
  <div class="badges">{skills_html}</div>
  <div class="stats">
    <div class="stat"><div class="stat-n">{repos_count}</div><div class="stat-l">Repos</div></div>
    <div class="stat"><div class="stat-n">{followers}</div><div class="stat-l">Followers</div></div>
    <div class="stat"><div class="stat-n">{following}</div><div class="stat-l">Following</div></div>
  </div>
  <div class="repos">
    <div class="label">🏆 Top Repos</div>
    <ul>{repos_html}</ul>
  </div>
  {f'<div class="fun">💡 {fun}</div>' if fun else ''}
  {f'<div class="info">{info_line}</div>' if info_line else ''}
  <div class="footer">
    <a class="gh-link" href="https://github.com/{username}" target="_blank">🔗 github.com/{username}</a>
    <span class="watermark">Dev Card Generator</span>
  </div>
</div></body></html>"""

@mcp.tool()
async def save_card(username: str, html: str) -> str:
    """Saves the card HTML to disk and returns the URL path."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cards_dir = os.path.join(script_dir, "static", "cards")
    os.makedirs(cards_dir, exist_ok=True)
    path = os.path.join(cards_dir, f"{username}.html")
    with open(path, "w") as f:
        f.write(html)
    return f"/card/{username}"


if __name__ == "__main__":
    mcp.run()
