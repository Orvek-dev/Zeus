from __future__ import annotations

from zeus_agent.objective_risk_runtime import (
    BlastRadius,
    Irreversibility,
    Resolution,
    RiskClass,
    RiskContext,
    SafeDefault,
    Triage,
    Unknown,
    assess_objective_risk,
    impact,
    voi_score,
)


def _unknown(unknown_id: str, risk_class: RiskClass, **overrides: object) -> Unknown:
    base: dict[str, object] = {
        "unknown_id": unknown_id,
        "description": "missing {0}".format(unknown_id),
        "risk_class": risk_class,
    }
    base.update(overrides)
    return Unknown(**base)  # type: ignore[arg-type]


# --- VoI arithmetic ---------------------------------------------------------


def test_impact_uses_exponential_weights() -> None:
    # Given: a public, irreversible, costly unknown.
    unknown = _unknown(
        "pub",
        RiskClass.quality,
        irreversibility=Irreversibility.high,
        blast_radius=BlastRadius.public,
        cost_bucket=5,
    )

    # Then: impact is 9 (irrev) x 9 (blast) x 5 (cost) — the worst pairing dominates.
    assert impact(unknown) == 405
    assert voi_score(unknown.model_copy(update={"failure_probability": 1.0})) == 405.0


def test_local_low_risk_unknown_has_tiny_voi() -> None:
    unknown = _unknown(
        "local",
        RiskClass.time,
        irreversibility=Irreversibility.low,
        blast_radius=BlastRadius.local,
        cost_bucket=1,
        failure_probability=0.4,
    )
    assert voi_score(unknown) == 0.4


# --- Fail-closed hard rules (override-locked) -------------------------------


def test_external_effect_without_default_is_locked_question() -> None:
    # Given: an external publish target with no safe default, in one-shot work
    # (the highest threshold, where VoI alone would never ask).
    profile = assess_objective_risk(
        triage=Triage.oneshot,
        unknowns=(_unknown("publish_target", RiskClass.external),),
    )

    # Then: it is asked anyway, marked override-locked, and blocks proceed.
    resolution = profile.resolutions[0]
    assert resolution.resolution is Resolution.question
    assert resolution.override_locked is True
    assert resolution.reasons == ("external_effect_target_unspecified",)
    assert profile.proceed_allowed_without_answers is False


def test_cost_without_cap_is_locked_question() -> None:
    profile = assess_objective_risk(
        triage=Triage.oneshot,
        unknowns=(_unknown("spend_cap", RiskClass.cost),),
    )
    resolution = profile.resolutions[0]
    assert resolution.resolution is Resolution.question
    assert resolution.override_locked is True
    assert "cost_cap_unspecified" in resolution.reasons


def test_just_do_it_cannot_waive_locked_external_question() -> None:
    # Given: the user says "just do it" but the external target has no default.
    profile = assess_objective_risk(
        triage=Triage.automation,
        unknowns=(_unknown("transfer_target", RiskClass.external),),
        override_just_do_it=True,
    )

    # Then: the override is ignored for the locked question.
    assert profile.resolutions[0].resolution is Resolution.question
    assert profile.proceed_allowed_without_answers is False


def test_external_effect_with_default_can_be_assumed() -> None:
    # Given: an external unknown that DOES have a safe default (e.g. the single
    # already-connected account).
    unknown = _unknown(
        "publish_account",
        RiskClass.external,
        safe_default=SafeDefault(value="the one connected blog", rationale="only candidate"),
    )
    profile = assess_objective_risk(triage=Triage.automation, unknowns=(unknown,))

    # Then: it is not hard-locked; low VoI lets it assume.
    assert profile.resolutions[0].override_locked is False
    assert profile.resolutions[0].resolution is Resolution.assume


# --- Cross-class rules R2 / R3 ----------------------------------------------


def test_sensitive_data_to_external_sink_is_locked_r2() -> None:
    unknown = _unknown(
        "customer_data",
        RiskClass.data,
        sensitive=True,
        feeds_external_sink=True,
        safe_default=SafeDefault(value="redact", rationale="default"),
    )
    profile = assess_objective_risk(triage=Triage.oneshot, unknowns=(unknown,))
    assert profile.resolutions[0].resolution is Resolution.question
    assert profile.resolutions[0].override_locked is True
    assert "sensitive_data_flows_to_external_sink" in profile.resolutions[0].reasons


def test_ambiguous_account_is_locked_r3() -> None:
    unknown = _unknown(
        "debit_account",
        RiskClass.access,
        multiple_account_candidates=True,
        safe_default=SafeDefault(value="first", rationale="default"),
    )
    profile = assess_objective_risk(triage=Triage.oneshot, unknowns=(unknown,))
    assert profile.resolutions[0].resolution is Resolution.question
    assert profile.resolutions[0].override_locked is True


# --- Cross-class rules R1 / R4 (numeric context) ----------------------------


def test_time_assumption_escalates_when_periodicity_breaches_budget_r1() -> None:
    # Given: a frequency unknown that would normally be assumed...
    frequency = _unknown(
        "frequency",
        RiskClass.time,
        blast_radius=BlastRadius.account,
        cost_bucket=2,
        failure_probability=0.4,
        safe_default=SafeDefault(value="twice weekly", rationale="conservative"),
    )
    # ...but the projected cost overruns the cap.
    context = RiskContext(projected_cost_units=120, budget_cap_units=50)
    profile = assess_objective_risk(
        triage=Triage.automation, unknowns=(frequency,), context=context
    )
    assert profile.resolutions[0].resolution is Resolution.question
    assert "periodicity_breaches_budget" in profile.resolutions[0].reasons


def test_quality_sample_escalates_when_sample_too_expensive_r4() -> None:
    quality = _unknown("tone", RiskClass.quality, sample_learnable=True)
    context = RiskContext(sample_cost_units=20, single_run_cap_units=8)
    profile = assess_objective_risk(triage=Triage.project, unknowns=(quality,), context=context)
    assert profile.resolutions[0].resolution is Resolution.question
    assert "sample_cost_exceeds_cap" in profile.resolutions[0].reasons


def test_quality_unknown_is_learned_by_sample_by_default() -> None:
    quality = _unknown("tone", RiskClass.quality, sample_learnable=True)
    profile = assess_objective_risk(triage=Triage.automation, unknowns=(quality,))
    assert profile.resolutions[0].resolution is Resolution.learn_by_sample
    assert any("tone" in line for line in profile.assumptions)


# --- Threshold varies by triage ---------------------------------------------


def test_same_unknown_asked_in_automation_assumed_in_oneshot() -> None:
    # An account-blast, mid-impact unknown WITH a safe default sits between the
    # automation threshold (6) and the one-shot threshold (24).
    unknown = _unknown(
        "refresh_window",
        RiskClass.time,
        irreversibility=Irreversibility.medium,
        blast_radius=BlastRadius.account,
        cost_bucket=1,
        failure_probability=1.0,
        safe_default=SafeDefault(value="business hours", rationale="safe"),
    )
    # impact = 3 x 3 x 1 = 9, VoI = 9.0
    assumed = assess_objective_risk(triage=Triage.oneshot, unknowns=(unknown,))
    asked = assess_objective_risk(triage=Triage.automation, unknowns=(unknown,))
    assert assumed.resolutions[0].resolution is Resolution.assume
    assert asked.resolutions[0].resolution is Resolution.question
    assert asked.resolutions[0].override_locked is False


# --- Paper tests: question count is DERIVED, never fixed ---------------------


def test_paper_blog_automation_asks_exactly_two() -> None:
    # "ai로 블로그 자동화하고싶어" — only the two hard rules fire.
    unknowns = (
        _unknown("publish_target", RiskClass.external),  # locked
        _unknown("spend_cap", RiskClass.cost),  # locked
        _unknown(
            "frequency",
            RiskClass.time,
            blast_radius=BlastRadius.account,
            cost_bucket=2,
            failure_probability=0.4,
            safe_default=SafeDefault(value="twice weekly", rationale="conservative"),
        ),
        _unknown("tone", RiskClass.quality, sample_learnable=True),
    )
    profile = assess_objective_risk(triage=Triage.automation, unknowns=unknowns)
    assert profile.blocking_question_count == 2
    # External is surfaced before cost (class priority on VoI tie).
    assert profile.questions[0] == "missing publish_target"
    assert profile.proceed_allowed_without_answers is False


def test_paper_bank_transfer_asks_more() -> None:
    # "은행 이체 자동화" — several high-stakes classes fire.
    unknowns = (
        _unknown("transfer_target", RiskClass.external),
        _unknown("amount_limit", RiskClass.cost),
        _unknown("debit_account", RiskClass.access, multiple_account_candidates=True,
                  safe_default=SafeDefault(value="first", rationale="default")),
        _unknown("statement_data", RiskClass.data, sensitive=True, feeds_external_sink=True,
                  safe_default=SafeDefault(value="redact", rationale="default")),
    )
    profile = assess_objective_risk(triage=Triage.automation, unknowns=unknowns)
    assert profile.blocking_question_count == 4
    assert all(item.override_locked for item in profile.resolutions)


def test_paper_tidy_downloads_asks_nothing() -> None:
    # "내 다운로드 폴더 정리해줘" — every unknown has a safe local default.
    unknowns = (
        _unknown(
            "target_folder",
            RiskClass.external,
            blast_radius=BlastRadius.local,
            irreversibility=Irreversibility.medium,
            safe_default=SafeDefault(value="~/Downloads", rationale="named in request"),
        ),
        _unknown(
            "sort_scheme",
            RiskClass.quality,
            sample_learnable=True,
        ),
    )
    profile = assess_objective_risk(triage=Triage.oneshot, unknowns=unknowns)
    assert profile.blocking_question_count == 0
    assert profile.proceed_allowed_without_answers is True


def test_just_do_it_collapses_soft_questions_to_assumptions() -> None:
    # A non-locked, high-VoI unknown WITH a safe default becomes an assumption
    # under override; a locked one in the same batch still blocks.
    unknowns = (
        _unknown(
            "refresh_window",
            RiskClass.time,
            irreversibility=Irreversibility.high,
            blast_radius=BlastRadius.account,
            cost_bucket=3,
            failure_probability=1.0,
            safe_default=SafeDefault(value="hourly", rationale="safe"),
        ),
        _unknown("publish_target", RiskClass.external),  # locked
    )
    profile = assess_objective_risk(
        triage=Triage.automation, unknowns=unknowns, override_just_do_it=True
    )
    by_id = {item.unknown_id: item for item in profile.resolutions}
    assert by_id["refresh_window"].resolution is Resolution.assume
    assert by_id["publish_target"].resolution is Resolution.question
    assert profile.blocking_question_count == 1
    assert profile.proceed_allowed_without_answers is False
