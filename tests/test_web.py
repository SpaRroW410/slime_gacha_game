"""The JSON command API used by the browser (webapi.py) and the local server (serve.py)."""
import json
import os
import sys
import threading
import unittest
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha.webapi import HANDLERS, Session, snapshot


def session(seed=8, pulls=10, gel=500):
    s = Session()
    assert s.call("new_game", {"seed": seed})["ok"]
    s.game.wallet.add("white_gel", gel)
    s.game.wallet.add("food", 300)
    s.game.wallet.add("essence", 300)
    s.game.needs.auto_care = False
    s.game.forage = False
    if pulls:
        assert s.call("pull", {"n": pulls, "pay": "white_gel"})["ok"]
    return s


class TestEnvelope(unittest.TestCase):
    def test_needs_a_game_first(self):
        r = Session().call("state")
        self.assertFalse(r["ok"])
        self.assertIn("No game", r["error"])

    def test_new_game_and_state_are_json_serialisable(self):
        s = Session()
        r = s.call("new_game", {"seed": 1, "party_size": 10})
        self.assertTrue(r["ok"])
        self.assertEqual(r["state"]["party_size"], 10)
        json.dumps(r)                                  # the whole envelope must serialise
        s.call("pull", {"n": 1, "pay": "free"})
        json.dumps(s.call("state"))

    def test_bad_party_size_is_an_error_not_a_crash(self):
        r = Session().call("new_game", {"party_size": 7})
        self.assertFalse(r["ok"])
        self.assertIn("multiple of 5", r["error"])

    def test_domain_errors_become_ok_false(self):
        s = session(pulls=0)
        r = s.call("pull", {"n": 1, "pay": "free"})
        self.assertTrue(r["ok"])
        r = s.call("pull", {"n": 1, "pay": "free"})
        self.assertFalse(r["ok"])
        self.assertIn("free pull", r["error"])
        self.assertIsNotNone(r["state"])               # UI can still render
        self.assertFalse(s.call("feed", {"id": 999})["ok"])
        self.assertFalse(s.call("hunt", {"id": 1, "zone": "mars"})["ok"])
        self.assertFalse(s.call("nope")["ok"])
        self.assertFalse(s.call("feed", {})["ok"])

    def test_call_json_roundtrip(self):
        s = session(pulls=1)
        out = json.loads(s.call_json("state", "{}"))
        self.assertTrue(out["ok"])
        out = json.loads(s.call_json("feed", json.dumps({"id": s.game.slimes()[0].id})))
        self.assertTrue(out["ok"])


class TestSaveLoad(unittest.TestCase):
    def test_save_in_response_reloads_into_a_fresh_session(self):
        s = session()
        sid = s.game.slimes()[0].id
        s.call("party_create", {"name": "A"})
        s.call("party_fill", {"pid": 1})
        s.call("wait", {"hours": 5})
        res = s.call("wait", {"hours": 1})
        save = json.loads(json.dumps(res["save"]))      # as the browser stores it
        t = Session()
        self.assertTrue(t.call("load", {"save": save})["ok"])
        a, b = res["state"], t.call("state")["state"]
        self.assertEqual(a["tick"], b["tick"])
        self.assertEqual([x["id"] for x in a["slimes"]], [x["id"] for x in b["slimes"]])
        self.assertEqual(a["parties"], b["parties"])
        self.assertEqual(a["wallet"], b["wallet"])


class TestCommands(unittest.TestCase):
    def test_colony_commands(self):
        s = session()
        sl = s.game.slimes()
        a, b = sl[0].id, sl[1].id
        for cmd, args in [("feed", dict(id=a)), ("pet", dict(id=a)), ("sleep", dict(id=a)), ("wake", dict(id=a)),
                          ("stance", dict(id=a, stance="defend")), ("rest", dict(id=a)), ("wake", dict(id=a)),
                          ("hunt", dict(id=b, zone="meadow")), ("recall", dict(id=b)),
                          ("auto_care", dict(on=True)), ("wait", dict(hours=3)), ("compat", dict(a=a, b=b)),
                          ("council", {})]:
            r = s.call(cmd, args)
            self.assertTrue(r["ok"], (cmd, r["error"]))
        self.assertEqual(s.call("stance", dict(id=a, stance="defend", _sel=a))["state"]["slimes"][0]["behavior"], "defend")
        self.assertEqual(s.call("wait", dict(hours=500))["log"][0], "72 hour(s) pass.")   # clamped

    def test_party_and_spar_and_battle_payload(self):
        s = session()
        r = s.call("party_create", {"name": "Vanguard"})
        self.assertTrue(r["ok"])
        self.assertEqual(s.call("party_fill", {"pid": 1})["log"], ["Added 5 slime(s) to the party."])
        st = s.call("state")["state"]
        self.assertTrue(st["parties"][0]["full"])
        a, b = st["parties"][0]["members"][:2]
        r = s.call("spar", {"a": a, "b": b, "discipline": "sword"})
        self.assertTrue(r["ok"])
        self.assertNotIn("battle", r["result"])                         # the duel report arrives when the duellists are back
        self.assertFalse(s.call("spar", {"a": a, "b": a, "discipline": "sword"})["ok"])
        away = s.call("state")["state"]["away"]
        self.assertTrue(any(x["kind"] == "expedition" and x["hours"] > 0 for x in away))     # the duellists are away with the hours left
        s.call("wait", {"hours": 3})
        r = s.call("skirmish", {"pid": 1, "tier": 1})
        self.assertTrue(r["ok"])
        self.assertNotIn("battle", r["result"])                         # the party is away: the report comes with it
        self.assertTrue(r["state"]["held"])
        w = s.call("wait", {"hours": r["state"]["held"][0]["hours"]})
        bat = w["state"]["reports"][0]["battles"][0]
        self.assertIn("log", bat)
        self.assertIn("victory", bat)
        for rep in w["state"]["reports"]:
            s.call("ack_report", {"id": rep["id"]})
        self.assertEqual(s.call("state")["state"]["reports"], [])

    def test_dungeon_commands(self):
        s = session()
        s.call("party_create", {"name": "V"})
        s.call("party_fill", {"pid": 1})
        plan = s.call("scout_plan", {"pid": 1, "first": 1, "last": 2})
        self.assertTrue(plan["ok"])
        self.assertGreater(plan["result"]["safe"], 0)
        r = s.call("scout", {"pid": 1, "first": 1, "last": 2, "hours": plan["result"]["safe"]})
        self.assertTrue(r["ok"], r["error"])
        self.assertIn("complete", r["result"])
        self.assertFalse(s.call("scout", {"pid": 1, "first": 1, "last": 2, "hours": 1})["ok"])   # below the minimum
        self.assertFalse(s.call("scout", {"pid": 1, "first": 5, "last": 5, "hours": 8})["ok"])   # floors not walked
        s.call("wait", {"hours": 48})                                                          # the scouts come home
        for sl in s.game.slimes():
            sl.hp, sl.state, sl.grounded = sl.max_hp, "idle", False
            sl.needs.v.update({k: 90.0 for k in sl.needs.v})
            sl.emotions.clear()
        g = s.call("grind", {"pid": 1, "depth": 2, "runs": 2})
        self.assertTrue(g["ok"], g["error"])
        self.assertNotIn("battle", g["result"])                          # held until the party is back
        self.assertTrue(g["state"]["held"])
        w = s.call("wait", {"hours": 72})
        self.assertTrue(w["state"]["reports"][0]["battles"])
        s.call("ack_report", {"id": w["state"]["reports"][0]["id"]})
        for sl in s.game.slimes():
            sl.hp, sl.state, sl.grounded, sl.sanity = sl.max_hp, "idle", False, 100.0
            sl.needs.v.update({k: 90.0 for k in sl.needs.v})
            sl.emotions.clear()
        s.call("party_fill", {"pid": 1})                                                        # (a scout may have fallen)
        e = s.call("enter_dungeon", {"pid": 1})
        self.assertTrue(e["ok"], e["error"])
        self.assertIn("1", e["state"]["dungeon"]["delves"])
        self.assertTrue(e["state"]["dungeon"]["delves"]["1"]["can_leave"])          # still at the entrance
        self.assertFalse(s.call("enter_dungeon", {"pid": 1, "start": 6})["ok"])
        self.assertTrue(e["state"]["parties"][0]["in_delve"])
        self.assertFalse(s.call("rest", {"id": s.game.party_members(1)[0].id})["ok"])      # locked in
        n = s.call("delve_next", {"pid": 1})
        self.assertTrue(n["ok"])
        self.assertNotIn("battle", n["result"])                          # the floor report arrives when the party is ready again
        busy = n["state"]["dungeon"]["delves"]["1"]["ready_in"]
        self.assertGreater(busy, 0)                                                             # the floor took game hours: the party is away
        w = s.call("wait", {"hours": busy})                                                     # ... until they pass
        self.assertTrue(w["state"]["reports"][0]["battles"][0]["log"])
        c = s.call("delve_camp", {"pid": 1, "hours": 2})
        self.assertTrue(c["ok"] or "not inside" in c["error"])
        d = c["state"]["dungeon"]["delves"].get("1")
        if d and not d["can_leave"]:
            self.assertFalse(s.call("leave_dungeon", {"pid": 1})["ok"])               # mid-segment: no way out

    def test_academy_town_council_commands(self):
        s = session()
        g = s.game
        sch = g.gacha.make_slime("rare", "barbarian", stars=3)
        g.roster[sch.id] = sch
        r = s.call("study", {"id": sch.id, "element": "fire"})
        self.assertTrue(r["ok"], r["error"])
        s.call("wait", {"hours": 4})
        sch.mastery_xp["fire"] = 130
        self.assertTrue(s.call("learn", {"id": sch.id, "spell": "ember"})["ok"])
        self.assertFalse(s.call("research_preview", {"id": sch.id, "a": "ember", "b": "ember"})["ok"])
        self.assertTrue(s.call("forget", {"id": sch.id, "spell": "ember"})["ok"])
        self.assertTrue(s.call("buy_gear", {"key": "wooden_club"})["ok"])
        self.assertTrue(s.call("equip", {"id": sch.id, "key": "wooden_club"})["ok"])
        v = [x for x in s.call("state")["state"]["slimes"] if x["id"] == sch.id][0]
        self.assertEqual(v["gear"], {"weapon": "wooden_club"})
        self.assertTrue(s.call("unequip", {"id": sch.id, "slot": "weapon"})["ok"])
        self.assertTrue(s.call("upgrade", {"key": "rest_area"})["ok"])
        self.assertFalse(s.call("upgrade", {"key": "castle"})["ok"])
        pv = s.call("merge_preview", {"target": g.slimes()[0].id, "donor": g.slimes()[1].id})
        self.assertTrue(pv["ok"])
        self.assertIn("xp", pv["result"])
        m = s.call("merge", {"target": g.slimes()[0].id, "donor": g.slimes()[1].id})
        self.assertTrue(m["ok"])
        self.assertGreater(m["state"]["stress"], 0)

    def test_every_command_is_registered_and_snapshot_has_ui_data(self):
        for cmd in ("pull", "hunt", "spar", "scout", "scout_plan", "leave_dungeon", "specialize", "grind",
                    "enter_dungeon", "delve_next", "delve_camp",
                    "study", "learn", "research", "upgrade", "buy_gear", "equip", "merge", "council", "mediate"):
            self.assertIn(cmd, HANDLERS)
        st = session()._ok([], {})["state"]
        for key in ("wallet", "slimes", "parties", "buildings", "dungeon", "gear", "zones", "disciplines",
                    "elements", "library", "free_pull", "stress", "rates", "stances", "spec", "outlooks"):
            self.assertIn(key, st)
        self.assertEqual(len(st["dungeon"]["floors"]), 10)
        self.assertIn("spec_options", st["slimes"][0])
        self.assertIn("outlook", st["slimes"][0])
        self.assertIn("progress", st["slimes"][0])


class TestServer(unittest.TestCase):
    def test_http_roundtrip_and_static_files(self):
        import serve
        from http.server import ThreadingHTTPServer
        srv = ThreadingHTTPServer(("127.0.0.1", 0), serve.Handler)
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            base = f"http://127.0.0.1:{port}"
            self.assertTrue(json.load(urllib.request.urlopen(base + "/api/ping"))["ok"])
            html = urllib.request.urlopen(base + "/").read().decode()
            self.assertIn("Slime Gacha", html)
            for f in ("app.js", "backend.js", "style.css"):
                self.assertEqual(urllib.request.urlopen(f"{base}/{f}").status, 200)
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(base + "/../serve.py")
            req = urllib.request.Request(base + "/api", data=json.dumps({"cmd": "new_game", "args": {"seed": 1}}).encode(),
                                         headers={"Content-Type": "application/json"})
            self.assertTrue(json.load(urllib.request.urlopen(req))["ok"])
            req = urllib.request.Request(base + "/api", data=json.dumps({"cmd": "pull", "args": {"n": 1, "pay": "free"}}).encode())
            r = json.load(urllib.request.urlopen(req))
            self.assertTrue(r["ok"])
            self.assertEqual(len(r["state"]["slimes"]), 1)
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main()


class TestSlimViews(unittest.TestCase):
    def test_state_is_slim_until_a_card_is_opened(self):
        s = session(pulls=20)
        light = s.call("state")
        self.assertIsNone(light["save"])                                  # a read changes nothing: no save to send
        v = light["state"]["slimes"][0]
        self.assertFalse(v["detail"])
        self.assertNotIn("power_parts", v)
        self.assertIn("value", v["prof"])                                 # avatars still get proficiency
        sid = v["id"]
        one = s.call("slime_detail", {"id": sid})["result"]["slime"]
        self.assertIn("power_parts", one)
        full = s.call("state", {"_sel": sid})["state"]["slimes"]
        self.assertTrue(next(x for x in full if x["id"] == sid)["detail"])
        self.assertEqual(sum(1 for x in full if x["detail"]), 1)
        self.assertIsNotNone(s.call("wait", {"hours": 1})["save"])        # a change does carry the save
