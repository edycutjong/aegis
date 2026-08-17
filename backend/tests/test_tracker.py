"""Tests for app.observability.tracker."""

from app.observability.tracker import (
    RequestMetrics,
    ObservabilityTracker,
    get_tracker,
)


class TestRequestMetrics:
    """Verify per-request metrics accumulation."""

    def test_add_step_accumulates_tokens(self):
        m = RequestMetrics(thread_id="t1")
        m.add_step("classify_intent", "llama-3.1-8b-instant", 100, 50)
        m.add_step("write_sql", "gpt-4.1", 500, 200)

        assert m.total_prompt_tokens == 600
        assert m.total_completion_tokens == 250
        assert len(m.steps) == 2

    def test_add_step_tracks_cost(self):
        m = RequestMetrics(thread_id="t1")
        # llama-3.1-8b: input 0.05/1M, output 0.08/1M
        m.add_step("classify_intent", "llama-3.1-8b-instant", 1_000_000, 1_000_000)
        assert m.total_cost_usd == round(0.05 + 0.08, 6)

    def test_add_step_tracks_model_distribution(self):
        m = RequestMetrics(thread_id="t1")
        m.add_step("step1", "gpt-4.1", 100, 50)
        m.add_step("step2", "gpt-4.1", 100, 50)
        m.add_step("step3", "llama-3.1-8b-instant", 100, 50)

        assert m.models_used == {"gpt-4.1": 2, "llama-3.1-8b-instant": 1}

    def test_to_dict_serialization(self):
        m = RequestMetrics(thread_id="t1")
        m.add_step("classify", "llama-3.1-8b-instant", 100, 50)
        d = m.to_dict()

        assert d["thread_id"] == "t1"
        assert d["total_prompt_tokens"] == 100
        assert d["total_completion_tokens"] == 50
        assert d["total_tokens"] == 150
        assert "steps" in d
        assert d["cache_hit"] is False
        assert d["approved"] is None

    def test_duration_seconds(self):
        m = RequestMetrics(thread_id="t1")
        m.started_at = 1000.0
        m.completed_at = 1002.5
        assert m.duration_seconds == 2.5

    def test_complete_sets_timestamp(self):
        m = RequestMetrics(thread_id="t1")
        assert m.completed_at is None
        m.complete()
        assert m.completed_at is not None
        assert m.completed_at >= m.started_at

    def test_to_dict_hitl_wait_seconds_when_both_timestamps_set(self):
        """to_dict should compute hitl_wait_seconds when both HITL timestamps are present."""
        m = RequestMetrics(thread_id="t1")
        m.hitl_requested_at = 1000.0
        m.hitl_resolved_at = 1004.25
        d = m.to_dict()
        assert d["hitl_wait_seconds"] == 4.25

    def test_to_dict_hitl_wait_seconds_none_when_only_requested(self):
        """hitl_wait_seconds should be None if only requested_at is set."""
        m = RequestMetrics(thread_id="t1")
        m.hitl_requested_at = 1000.0
        d = m.to_dict()
        assert d["hitl_wait_seconds"] is None


class TestObservabilityTracker:
    """Verify the aggregate tracker lifecycle."""

    def test_start_and_get_request(self):
        tracker = ObservabilityTracker()
        m = tracker.start_request("thread-1")
        assert tracker.get_request("thread-1") is m

    def test_get_nonexistent_request(self):
        tracker = ObservabilityTracker()
        assert tracker.get_request("nonexistent") is None

    def test_complete_request_moves_to_history(self):
        tracker = ObservabilityTracker()
        m = tracker.start_request("thread-1")
        m.add_step("classify", "llama-3.1-8b-instant", 100, 50)

        tracker.complete_request("thread-1")

        assert tracker.get_request("thread-1") is None
        assert len(tracker._history) == 1

    def test_aggregate_stats_empty(self):
        tracker = ObservabilityTracker()
        stats = tracker.get_aggregate_stats()
        assert stats["total_requests"] == 0
        assert stats["avg_cost_usd"] == 0.0

    def test_aggregate_stats_with_data(self):
        tracker = ObservabilityTracker()

        for i in range(3):
            m = tracker.start_request(f"t{i}")
            m.add_step("classify", "llama-3.1-8b-instant", 1000, 500)
            tracker.complete_request(f"t{i}")

        stats = tracker.get_aggregate_stats()
        assert stats["total_requests"] == 3
        assert stats["total_cost_usd"] > 0
        assert "llama-3.1-8b-instant" in stats["model_distribution"]

    def test_aggregate_stats_averaging_math(self):
        """avg_cost_usd and avg_duration_seconds should equal total / count."""
        tracker = ObservabilityTracker()

        for i in range(4):
            m = tracker.start_request(f"t{i}")
            m.started_at = 1000.0
            m.add_step("classify", "llama-3.1-8b-instant", 1_000_000, 1_000_000)
            tracker.complete_request(f"t{i}")

        stats = tracker.get_aggregate_stats()
        per_request_cost = round(0.05 + 0.08, 6)
        assert stats["avg_cost_usd"] == per_request_cost
        assert stats["total_cost_usd"] == round(per_request_cost * 4, 6)

    def test_model_distribution_multi_model(self):
        """model_distribution should aggregate counts across multiple requests."""
        tracker = ObservabilityTracker()

        m1 = tracker.start_request("t1")
        m1.add_step("classify", "llama-3.1-8b-instant", 100, 50)
        m1.add_step("write_sql", "gpt-4.1", 500, 200)
        tracker.complete_request("t1")

        m2 = tracker.start_request("t2")
        m2.add_step("classify", "llama-3.1-8b-instant", 100, 50)
        m2.add_step("propose", "gpt-4.1", 500, 200)
        m2.add_step("respond", "llama-3.1-8b-instant", 100, 50)
        tracker.complete_request("t2")

        stats = tracker.get_aggregate_stats()
        dist = stats["model_distribution"]
        assert dist["llama-3.1-8b-instant"] == 3  # 1 + 2
        assert dist["gpt-4.1"] == 2  # 1 + 1

    def test_hitl_approval_rate_computed_from_approved_requests(self):
        """hitl_approval_rate should reflect the fraction of HITL requests approved."""
        tracker = ObservabilityTracker()

        m1 = tracker.start_request("t1")
        m1.approved = True
        tracker.complete_request("t1")

        m2 = tracker.start_request("t2")
        m2.approved = False
        tracker.complete_request("t2")

        m3 = tracker.start_request("t3")
        m3.approved = True
        tracker.complete_request("t3")

        # A non-HITL request (approved stays None) should not count toward the rate
        tracker.start_request("t4")
        tracker.complete_request("t4")

        stats = tracker.get_aggregate_stats()
        assert stats["hitl_approval_rate"] == round(2 / 3 * 100, 1)

    def test_hitl_approval_rate_none_when_no_hitl_requests(self):
        """hitl_approval_rate should be None when no request ever went through HITL."""
        tracker = ObservabilityTracker()
        m = tracker.start_request("t1")
        m.add_step("classify", "llama-3.1-8b-instant", 100, 50)
        tracker.complete_request("t1")

        stats = tracker.get_aggregate_stats()
        assert stats["hitl_approval_rate"] is None

    def test_avg_hitl_wait_seconds_computed(self):
        """avg_hitl_wait_seconds should average hitl_wait_seconds across completed requests."""
        tracker = ObservabilityTracker()

        m1 = tracker.start_request("t1")
        m1.hitl_requested_at = 1000.0
        m1.hitl_resolved_at = 1002.0  # 2s wait
        tracker.complete_request("t1")

        m2 = tracker.start_request("t2")
        m2.hitl_requested_at = 2000.0
        m2.hitl_resolved_at = 2006.0  # 6s wait
        tracker.complete_request("t2")

        # Request without HITL timing should be excluded from the average
        tracker.start_request("t3")
        tracker.complete_request("t3")

        stats = tracker.get_aggregate_stats()
        assert stats["avg_hitl_wait_seconds"] == 4.0

    def test_avg_hitl_wait_seconds_none_when_no_hitl_timing(self):
        """avg_hitl_wait_seconds should be None when no request recorded HITL timing."""
        tracker = ObservabilityTracker()
        tracker.start_request("t1")
        tracker.complete_request("t1")

        stats = tracker.get_aggregate_stats()
        assert stats["avg_hitl_wait_seconds"] is None


class TestGetTracker:
    def test_returns_singleton(self):
        t1 = get_tracker()
        t2 = get_tracker()
        assert t1 is t2
