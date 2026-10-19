"""Offline checks of target timing, scoring, leakage boundaries and API audit behavior."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import pandas as pd
from . import data,strategy,evaluate

class BenchmarkChecks(unittest.TestCase):
    def test_holiday_and_fifth_session(self):
        w=data.target_window("2024-07-03T23:59:59-04:00")
        self.assertEqual(w["entry_session"],"2024-07-05")
        self.assertEqual(w["exit_session"],"2024-07-11")
        self.assertEqual(len(w["sessions"]),5)
    def test_intraday_open_is_not_executable(self):
        self.assertEqual(data.target_window("2024-07-05T10:00:00-04:00")["entry_session"],"2024-07-08")
    def test_early_morning_uses_same_day_open(self):
        self.assertEqual(data.target_window("2024-07-05T08:00:00-04:00")["entry_session"],"2024-07-05")
    def test_dst_and_weekend(self):
        w=data.target_window("2024-03-08T23:59:59-05:00")
        self.assertEqual(w["entry_open_at"],"2024-03-11T13:30:00+00:00")
    def test_price_label_and_split_exclusion(self):
        case={"case_id":"x","window":{"entry_session":"2024-01-02","exit_session":"2024-01-08","sessions":["2024-01-02","2024-01-08"]}}
        bars=[{"date":"2024-01-02","open":100,"close":100,"split":0},{"date":"2024-01-08","open":102,"close":102,"split":0}]
        self.assertEqual(data.label_case(case,bars)["label"],"up")
        bars[1]["split"]=2
        self.assertEqual(data.label_case(case,bars)["status"],"split_in_target_window")
    def test_missing_bar_never_filled(self):
        c={"case_id":"x","window":{"entry_session":"2024-01-02","exit_session":"2024-01-08","sessions":[]}}
        self.assertEqual(data.label_case(c,[])["status"],"missing_target_bar")
    def test_perfect_and_worst_brier(self):
        o={"x":{"label":"up","status":"ok","return":0.1}}
        self.assertEqual(evaluate.score(["x"],{"x":{"up":1,"flat":0,"down":0}},o)["brier"],0)
        self.assertEqual(evaluate.score(["x"],{"x":{"up":0,"flat":0,"down":1}},o)["brier"],2)
    def test_failure_cannot_improve_selection(self):
        o={"x":{"label":"up","status":"ok"},"y":{"label":"down","status":"ok"}}
        m=evaluate.score(["x","y"],{"x":{"up":1,"flat":0,"down":0}},o)
        self.assertEqual(m["brier"],0)
        self.assertEqual(m["forecast_coverage"],0.5)
        self.assertEqual(m["selection_brier_failure_penalized"],1)
    def test_bad_probabilities_not_normalized(self):
        self.assertIsNone(evaluate.checked_probabilities({"up":0.5,"flat":0.4,"down":0.09}))
        self.assertIsNone(evaluate.checked_probabilities({"up":float("nan"),"flat":0,"down":1}))
    def test_flat_and_abstention_differ(self):
        o={"x":{"label":"flat","status":"ok"},"y":{"label":"up","status":"ok"}}
        m=evaluate.score(["x","y"],{"x":{"up":0.2,"flat":0.6,"down":0.2},"y":{"up":0.34,"flat":0.33,"down":0.33}},o)
        self.assertEqual(m["abstention_policy"]["accepted"],1)
        self.assertEqual(m["abstention_policy"]["conditional_accuracy"],1)
    def test_prior_uses_training_ids_only(self):
        out={"train":{"label":"flat"},"validation":{"label":"down"}}
        self.assertEqual(evaluate.training_prior(["train"],out),{"up":0,"flat":1,"down":0})
    def test_state_allowlist_discards_outcomes(self):
        case={"label":"up","return":0.5,"entry_open":10,"exit_close":15,"company":{"name":"X"},"articles":[{"text":"Evidence","label":"down","future_price":90}],"window":{"entry_open":10}}
        state=strategy.safe_state(case)
        self.assertNotIn("label",state);self.assertNotIn("window",state)
        self.assertNotIn("future_price",state["articles"][0]);self.assertNotIn("label",state["articles"][0])
    def test_future_price_perturbation_does_not_change_features(self):
        sessions=data.CAL.sessions_in_range("2024-01-01","2024-03-01")
        bars=[{"date":s.date().isoformat(),"close":100+i} for i,s in enumerate(sessions)]
        case={"decision_time":"2024-02-01T23:59:59-05:00"}
        a=data.market_features(case,bars,bars)
        changed=[{**r,"close":999999 if r["date"]>"2024-02-01" else r["close"]} for r in bars]
        self.assertEqual(a,data.market_features(case,changed,changed))
    def test_return_boundary_is_inclusive(self):
        c={"case_id":"x","window":{"entry_session":"2024-01-02","exit_session":"2024-01-08","sessions":["2024-01-02","2024-01-08"]}}
        for exit in (99,101):
            bars=[{"date":"2024-01-02","open":100,"close":100,"split":0},{"date":"2024-01-08","open":100,"close":exit,"split":0}]
            self.assertEqual(data.label_case(c,bars)["label"],"flat")
    def test_rejected_attempt_is_preserved_and_success_cached(self):
        class Response:
            status_code=200;headers={}
            def __init__(self,p):self.p=p
            def json(self):return self.p
        questions={"x":{"type":"choice","instructions":"Choose","criteria":{"up":"up","flat":"flat","down":"down"}}}
        good={"model":"jev-1.13.0","answers":{"x":{"type":"choice","choice":"up","confidence":0.7,"probabilities":{"up":0.7,"flat":0.2,"down":0.1}}},"usage":{"input_tokens":5,"output_tokens":2}}
        bad=copy.deepcopy(good);bad["answers"]["x"]["probabilities"]["up"]=0.69
        with tempfile.TemporaryDirectory() as tmp,patch.object(strategy,"ROOT",Path(tmp)),patch.object(strategy,"_KEY","test-only"),patch.object(strategy.time,"sleep"),patch.object(strategy.requests,"post",side_effect=[Response(bad),Response(good)]) as post:
            first,key=strategy.call_jev({"text":"abc"},questions)
            second,_=strategy.call_jev({"text":"abc"},questions)
            self.assertEqual(first,good);self.assertEqual(second,good);self.assertEqual(post.call_count,2)
            import json
            record=json.loads((Path(tmp)/"records"/"api_cache"/(key+".json")).read_text(encoding="utf-8"))
            self.assertEqual(len(record["attempts"]),2);self.assertEqual(record["attempts"][0]["status"],"rejected")

if __name__=="__main__":unittest.main()
