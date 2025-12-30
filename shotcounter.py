#!/usr/bin/env python3
"""
ShotCounter - Team-based drink counter web app
"""

import json
import os
import threading
import uuid
from flask import Flask, jsonify, request, redirect, render_template

app = Flask(__name__)

DATA_FILE = "teams.json"
data_lock = threading.Lock()


def load_teams():
    """Load team data from JSON file."""
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_teams(teams):
    """Save team data to JSON file."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(teams, f, indent=2, ensure_ascii=False)


@app.route("/")
def root():
    # Redirect root to presentation view
    return redirect("/index")


@app.route("/admin")
def admin_view():
    return render_template("admin.html")


@app.route("/index")
def presentation_view():
    return render_template("presentation.html")


# ---------- API ENDPOINTS ----------


@app.route("/api/teams", methods=["GET"])
def api_get_teams():
    """Return list of visible teams sorted by score descending."""
    with data_lock:
        teams = load_teams()
    visible = [t for t in teams if not t.get("hidden", False)]
    visible.sort(key=lambda t: t.get("score", 0), reverse=True)
    return jsonify(visible)


@app.route("/api/team", methods=["POST"])
def api_add_team():
    """Add a new team (name in JSON body)."""
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()

    if not name:
        return jsonify({"status": "error", "message": "Team name is required"}), 400

    with data_lock:
        teams = load_teams()
        # avoid duplicate visible names
        for t in teams:
            if not t.get("hidden", False) and t.get("name", "").lower() == name.lower():
                return jsonify({"status": "error", "message": "Team already exists"}), 400

        team = {
            "id": str(uuid.uuid4()),
            "name": name,
            "score": 0,
            "hidden": False,
        }
        teams.append(team)
        save_teams(teams)

    return jsonify({"status": "ok", "team": team})


@app.route("/api/score", methods=["POST"])
def api_change_score():
    """Change score for a team by delta (JSON: {id, delta})."""
    data = request.get_json(force=True, silent=True) or {}
    team_id = data.get("id")
    delta = data.get("delta")

    try:
        delta = int(delta)
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Invalid delta"}), 400

    if not team_id:
        return jsonify({"status": "error", "message": "Missing team id"}), 400

    with data_lock:
        teams = load_teams()
        found = False
        for t in teams:
            if t.get("id") == team_id and not t.get("hidden", False):
                t["score"] = max(0, int(t.get("score", 0)) + delta)
                found = True
                break

        if not found:
            return jsonify({"status": "error", "message": "Team not found"}), 404

        save_teams(teams)

    return jsonify({"status": "ok"})


@app.route("/api/team/<team_id>/hide", methods=["POST"])
def api_hide_team(team_id):
    """Soft-delete (hide) a team."""
    with data_lock:
        teams = load_teams()
        found = False
        for t in teams:
            if t.get("id") == team_id:
                t["hidden"] = True
                found = True
                break

        if not found:
            return jsonify({"status": "error", "message": "Team not found"}), 404

        save_teams(teams)

    return jsonify({"status": "ok"})


# ---------- MAIN ----------

if __name__ == "__main__":
    # Create empty DB if not present
    if not os.path.exists(DATA_FILE):
        save_teams([])
    # Run Flask dev server
    app.run(host="0.0.0.0", port=8080, debug=True)
