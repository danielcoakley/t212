"""Deep research review gate page."""

from __future__ import annotations

import streamlit as st

from isa_system.dashboard.data import broker_snapshot, recommendation_workflow
from isa_system.services.deep_research import (
    DeepResearchReview,
    build_deep_research_input,
    latest_deep_research_review,
    run_deep_research,
)
from isa_system.services.portfolio_state import BrokerPortfolioSnapshot
from isa_system.services.recommendations import RecommendationAction, TradeRecommendation
from isa_system.utils.time import to_london


def render(
    snapshot: BrokerPortfolioSnapshot | None = None,
    *,
    candidates: tuple[str, ...] = (),
    include_defaults: bool = True,
    include_llm: bool = False,
) -> None:
    """Render selected-candidate thesis validation and research gate status."""

    snapshot = snapshot or broker_snapshot()
    st.title("Research Review")
    st.caption(
        "Deep research validates a buy/add thesis before preview sizing. It is an evidence "
        "gate only, not investment advice and not order authority."
    )

    progress = st.progress(0, text="Checking cached recommendation evidence.")
    with st.status("Preparing research review context...", expanded=True) as status:
        st.write("Loading the same cached recommendation workflow used by the queue.")
        progress.progress(30, text="Loading recommendations and broker validation.")
        try:
            workflow = recommendation_workflow(
                snapshot,
                candidates=candidates,
                include_defaults=include_defaults,
                include_llm=include_llm,
            )
        except Exception as exc:
            progress.progress(100, text="Research review context failed to load.")
            status.update(label="Research review context failed.", state="error")
            st.error(
                "The research review context could not be prepared. Refresh the dashboard "
                "cache from the sidebar and try again."
            )
            with st.expander("Technical detail"):
                st.exception(exc)
            return
        progress.progress(70, text="Loading persisted deep research review status.")
        response = workflow.recommendations
        validation = workflow.instrument_validation
        handoff = workflow.handoff
        cache_time = to_london(workflow.cache_window.opened_at_utc)
        st.write(
            f"Using {workflow.cache_window.label.lower()} from {cache_time:%Y-%m-%d %H:%M %Z}."
        )
        st.write(f"Recommendation bundle source: {workflow.cache_source}.")
        progress.progress(100, text="Research review context ready.")
        status.update(label="Research review context ready.", state="complete", expanded=False)
    review_candidates = [
        item
        for item in response.recommendations
        if item.action in {RecommendationAction.REVIEW_BUY, RecommendationAction.WATCH}
    ]
    if not review_candidates:
        st.info("No buy/watch candidates are available for deep research right now.")
        return

    selected_symbol = st.selectbox(
        "Candidate",
        options=[item.candidate.research_symbol for item in review_candidates],
    )
    item = next(
        candidate
        for candidate in review_candidates
        if candidate.candidate.research_symbol == selected_symbol
    )
    validation_by_symbol = {row.research_symbol.upper(): row for row in validation.rows}
    handoff_by_symbol = {row.research_symbol.upper(): row for row in handoff.rows}
    key = item.candidate.research_symbol.upper()
    latest_review = latest_deep_research_review(item.candidate.research_symbol)

    _render_candidate_context(item)
    _render_latest_review(latest_review)

    disabled = item.action != RecommendationAction.REVIEW_BUY
    if st.button("Run deep research gate", disabled=disabled):
        handoff_row = handoff_by_symbol.get(key)
        request = build_deep_research_input(
            item,
            instrument_row=validation_by_symbol.get(key),
            blockers=handoff_row.blockers if handoff_row is not None else [],
        )
        with st.spinner("Running deep research review..."):
            latest_review = run_deep_research(request)
        st.success("Research review completed and persisted.")
        _render_latest_review(latest_review)
    if disabled:
        st.info("Deep research approval is only required for REVIEW_BUY or add candidates.")


def _render_candidate_context(item: TradeRecommendation) -> None:
    scores = item.scores
    cols = st.columns(5)
    cols[0].metric("Action", item.action.value)
    cols[1].metric("Composite", f"{scores.composite:.2f}")
    cols[2].metric(
        "Fundamental",
        _score(scores.fundamental_valuation.score),
    )
    cols[3].metric("Technical", _score(scores.technical.score))
    cols[4].metric("Catalysts", _score(scores.catalysts.score))
    st.subheader("Current Evidence")
    st.write(" ".join(item.rationale))
    if item.risk_flags:
        st.warning("Risk flags: " + ", ".join(item.risk_flags))
    if item.warnings:
        st.warning("Source warnings: " + "; ".join(item.warnings))


def _render_latest_review(review: DeepResearchReview | None) -> None:
    st.subheader("Latest Deep Research")
    if review is None:
        st.info("No persisted deep research review exists for this candidate.")
        return
    generated = to_london(review.generated_at_utc)
    expires = to_london(review.expires_at_utc)
    cols = st.columns(4)
    cols[0].metric("Status", review.status.value)
    cols[1].metric("Decision", review.decision.value if review.decision else "n/a")
    cols[2].metric("Score", str(review.final_score) if review.final_score is not None else "n/a")
    cols[3].metric("Expires", f"{expires:%Y-%m-%d}")
    st.caption(
        f"Generated by {review.model} at {generated:%Y-%m-%d %H:%M:%S %Z}; "
        f"evidence hash {review.evidence_hash[:12]}."
    )
    st.write(review.thesis)
    target_cols = st.columns(3)
    for column, target in zip(target_cols, review.price_targets, strict=False):
        label = target.label.title()
        value = "n/a" if target.price is None else f"{target.price:,.2f}"
        column.metric(f"{label} target", value)
        column.caption(target.rationale)
    detail_cols = st.columns(3)
    detail_cols[0].subheader("Drivers")
    detail_cols[0].write(review.key_drivers or ["No drivers supplied."])
    detail_cols[1].subheader("Risks")
    detail_cols[1].write(review.risks or ["No risks supplied."])
    detail_cols[2].subheader("Evidence gaps")
    detail_cols[2].write(review.evidence_gaps or ["No gaps supplied."])
    for warning in review.warnings:
        st.warning(warning)


def _score(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"


if __name__ == "__main__":
    render()
