#!/usr/bin/env python3
"""football-data.org v4 client for nanobot.

Usage:
    football_api.py matches --team TEAM [--status STATUS] [--days N]
    football_api.py today [--competition CODE]
    football_api.py live
    football_api.py standings --competition CODE
    football_api.py search-team QUERY
    football_api.py competitions
"""
import urllib.request
import urllib.parse
import json
import argparse
import sys
import os
from datetime import datetime, timedelta

BASE_URL = "https://api.football-data.org/v4"
API_KEY = os.environ.get("FOOTBALL_DATA_KEY", "")

# Free tier competitions
COMPETITIONS = {
    "brasileirao": "BSA",
    "serie a brazil": "BSA",
    "bsa": "BSA",
    "premier league": "PL",
    "pl": "PL",
    "la liga": "PD",
    "pd": "PD",
    "bundesliga": "BL1",
    "bl1": "BL1",
    "serie a": "SA",
    "sa": "SA",
    "ligue 1": "FL1",
    "fl1": "FL1",
    "eredivisie": "DED",
    "ded": "DED",
    "championship": "ELC",
    "elc": "ELC",
    "primeira liga": "PPL",
    "ppl": "PPL",
    "champions league": "CL",
    "cl": "CL",
    "world cup": "WC",
    "wc": "WC",
    "euro": "EC",
    "ec": "EC",
}

# Known team IDs (football-data.org IDs)
KNOWN_TEAMS = {}
# Will be populated by search; common ones cached after first lookup


def api_request(endpoint, params=None):
    if not API_KEY:
        print(json.dumps({"error": "FOOTBALL_DATA_KEY not set"}))
        sys.exit(1)

    query = urllib.parse.urlencode(params or {})
    url = f"{BASE_URL}/{endpoint}?{query}" if query else f"{BASE_URL}/{endpoint}"

    req = urllib.request.Request(url, headers={
        "X-Auth-Token": API_KEY,
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        try:
            err = json.loads(body)
            print(json.dumps({"error": err.get("message", str(e))}))
        except Exception:
            print(json.dumps({"error": f"HTTP {e.code}: {body[:200]}"}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


def resolve_competition(name):
    key = name.lower().strip()
    if key in COMPETITIONS:
        return COMPETITIONS[key]
    return name.upper()


def find_team_id(name):
    """Search for a team and return its ID."""
    # Search across free competitions
    for comp in ["BSA", "PL", "PD", "BL1", "SA", "FL1", "CL"]:
        data = api_request(f"competitions/{comp}/teams")
        teams = data.get("teams", [])
        for t in teams:
            if name.lower() in t["name"].lower() or name.lower() in t.get("shortName", "").lower():
                return t["id"], t["name"]
    return None, None


def cmd_matches(args):
    team_id = args.team_id
    team_name = args.team

    if not team_id:
        # Try to find team by name
        team_id, resolved_name = find_team_id(args.team)
        if not team_id:
            print(f"Team '{args.team}' not found in free tier competitions")
            sys.exit(1)
        team_name = resolved_name

    params = {}
    if args.status:
        params["status"] = args.status.upper()

    if args.days:
        today = datetime.now()
        params["dateFrom"] = today.strftime("%Y-%m-%d")
        params["dateTo"] = (today + timedelta(days=args.days)).strftime("%Y-%m-%d")

    data = api_request(f"teams/{team_id}/matches", params)
    matches = data.get("matches", [])

    if not matches:
        print(f"No matches found for {team_name}")
        return

    results = []
    for m in matches[:10]:
        result = {
            "date": m["utcDate"],
            "status": m["status"],
            "competition": m["competition"]["name"],
            "matchday": m.get("matchday"),
            "home": m["homeTeam"]["name"],
            "away": m["awayTeam"]["name"],
        }
        score = m.get("score", {})
        ft = score.get("fullTime", {})
        if ft.get("home") is not None:
            result["score"] = f"{ft['home']} x {ft['away']}"

        results.append(result)

    print(json.dumps(results, indent=2, ensure_ascii=False))


def cmd_today(args):
    today = datetime.now().strftime("%Y-%m-%d")
    params = {"dateFrom": today, "dateTo": today}

    if args.competition:
        code = resolve_competition(args.competition)
        data = api_request(f"competitions/{code}/matches", params)
    else:
        data = api_request("matches", params)

    matches = data.get("matches", [])

    if not matches:
        print("No matches today.")
        return

    results = []
    for m in matches:
        result = {
            "competition": m["competition"]["name"],
            "home": m["homeTeam"]["name"],
            "away": m["awayTeam"]["name"],
            "date": m["utcDate"],
            "status": m["status"],
        }
        score = m.get("score", {})
        ft = score.get("fullTime", {})
        if ft.get("home") is not None:
            result["score"] = f"{ft['home']} x {ft['away']}"

        results.append(result)

    print(json.dumps(results, indent=2, ensure_ascii=False))


def cmd_live(args):
    data = api_request("matches", {"status": "LIVE"})
    matches = data.get("matches", [])

    if not matches:
        print("No live games right now.")
        return

    results = []
    for m in matches:
        score = m.get("score", {})
        ft = score.get("fullTime", {})
        results.append({
            "competition": m["competition"]["name"],
            "home": m["homeTeam"]["name"],
            "away": m["awayTeam"]["name"],
            "score": f"{ft.get('home', '?')} x {ft.get('away', '?')}",
            "status": m["status"],
            "minute": m.get("minute"),
        })

    print(json.dumps(results, indent=2, ensure_ascii=False))


def cmd_standings(args):
    code = resolve_competition(args.competition)
    params = {}
    if args.season:
        params["season"] = args.season
    if args.matchday:
        params["matchday"] = args.matchday

    data = api_request(f"competitions/{code}/standings", params)
    standings_list = data.get("standings", [])

    if not standings_list:
        print("No standings data available")
        return

    # Get the TOTAL type standings (not HOME or AWAY)
    table = None
    for s in standings_list:
        if s.get("type") == "TOTAL":
            table = s.get("table", [])
            break
    if not table:
        table = standings_list[0].get("table", [])

    results = []
    for t in table:
        results.append({
            "rank": t["position"],
            "team": t["team"]["name"],
            "points": t["points"],
            "played": t["playedGames"],
            "won": t["won"],
            "draw": t["draw"],
            "lost": t["lost"],
            "gf": t["goalsFor"],
            "ga": t["goalsAgainst"],
            "gd": t["goalDifference"],
        })

    print(json.dumps(results, indent=2, ensure_ascii=False))


def cmd_search_team(args):
    query = args.query.lower()
    found = []

    for comp in ["BSA", "PL", "PD", "BL1", "SA", "FL1", "CL"]:
        try:
            data = api_request(f"competitions/{comp}/teams")
        except SystemExit:
            continue
        teams = data.get("teams", [])
        for t in teams:
            if query in t["name"].lower() or query in t.get("shortName", "").lower():
                found.append({
                    "id": t["id"],
                    "name": t["name"],
                    "shortName": t.get("shortName", ""),
                    "competition": comp,
                    "venue": t.get("venue", ""),
                })

    if not found:
        print(f"No teams matching '{args.query}' in free tier competitions")
    else:
        # Deduplicate by ID
        seen = set()
        unique = []
        for f in found:
            if f["id"] not in seen:
                seen.add(f["id"])
                unique.append(f)
        print(json.dumps(unique, indent=2, ensure_ascii=False))


def cmd_competitions(args):
    data = api_request("competitions")
    comps = data.get("competitions", [])

    results = []
    for c in comps:
        results.append({
            "code": c.get("code", ""),
            "name": c["name"],
            "area": c.get("area", {}).get("name", ""),
            "type": c.get("type", ""),
        })

    print(json.dumps(results, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="football-data.org v4 client")
    sub = parser.add_subparsers(dest="command", required=True)

    # matches (by team)
    p_match = sub.add_parser("matches", help="Get matches for a team")
    p_match.add_argument("--team", required=True, help="Team name to search")
    p_match.add_argument("--team-id", type=int, dest="team_id", help="Team ID (skip search)")
    p_match.add_argument("--status", help="SCHEDULED, LIVE, IN_PLAY, PAUSED, FINISHED, etc.")
    p_match.add_argument("--days", type=int, help="Look ahead N days from today")

    # today
    p_today = sub.add_parser("today", help="Today's matches")
    p_today.add_argument("--competition", help="Competition name or code")

    # live
    sub.add_parser("live", help="Live scores")

    # standings
    p_std = sub.add_parser("standings", help="League standings")
    p_std.add_argument("--competition", required=True, help="Competition name or code")
    p_std.add_argument("--season", type=int, help="Season year")
    p_std.add_argument("--matchday", type=int, help="Matchday number")

    # search
    p_st = sub.add_parser("search-team", help="Search for a team")
    p_st.add_argument("query", help="Team name to search")

    # competitions
    sub.add_parser("competitions", help="List available competitions")

    args = parser.parse_args()

    commands = {
        "matches": cmd_matches,
        "today": cmd_today,
        "live": cmd_live,
        "standings": cmd_standings,
        "search-team": cmd_search_team,
        "competitions": cmd_competitions,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
