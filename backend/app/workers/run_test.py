"""The `run_test` job: eight stages with per-stage persistence (resume without repeating paid LLM
calls), cancel checks between LLM batches and stages, live progress events."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import numpy as np
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import session_scope
from app.errors import ApiError, ErrorCode
from app.llm import tasks as llm_tasks
from app.llm.client import LLMClient
from app.logging_setup import test_id_var
from app.models import AdAnalysis, AdAsset, AdTest, Archetype, ArchetypeReaction, Report, RunResult, User
from app.security import now_utc
from app.services import audit as audit_service
from app.services import email_service, fx, media, settings_service, settings_versions, storage
from app.services.cancel import cancel_key
from app.services.redis_client import get_redis
from app.workers import report_pdf
from app.workers.progress import Publisher
from engine.simulation.results.aggregate import combine_platforms, confidence_label, run_batch_estimate, should_stop
from engine.simulation.population.archetypes import build_archetypes
from engine.simulation.results.evidence import EvidenceBuilder, build_evidence
from engine.simulation.population.builder import build_population
from engine.simulation.reaction.priors import priors_from_reactions
from engine.simulation.pipeline import calibrate_bias,population_seed, reference_ad, simulate_platform_audience, summarize
from engine.simulation.results.scoring import score_components
from engine.simulation.config.resolver import resolve
from engine.simulation.types import AdFeatures, ArchetypeTable, FrozenConfig, Population, ReactionPriors

log = logging.getLogger("advar.worker")

STAGE_PCT = {
    "prepare": (0, 5),
    "analyze_ad": (5, 12),
    "population": (12, 15),
    "archetypes": (15, 18),
    "react": (18, 50),
    "simulate": (50, 85),
    "explain": (85, 97),
    "export": (97, 100),
}


class Cancelled(Exception):
    """Raised between stages / LLM batches when the cancel flag or a status change is seen."""


class TestRun:
    def __init__(self, test_id: uuid.UUID) -> None:
        self.test_id = test_id
        self.settings = get_settings()
        self.redis = get_redis()
        self.publisher = Publisher(test_id)
        self.client = LLMClient(test_id=test_id)
        self.state: dict[str, Any] = {}
        self.cfg: FrozenConfig | None = None
        self.ad: AdFeatures | None = None
        self.assets: list[AdAsset] = []
        self.images: list[bytes] = []
        self.transcript: str = ""
        self.caption: str = ""
        self.populations: dict[tuple[str, int], Population] = {}
        self.tables: dict[tuple[str, int], ArchetypeTable] = {}
        self.priors: dict[tuple[str, int, str], ReactionPriors] = {}
        self.reactions: dict[tuple[str, int, str], list[dict[str, Any] | None]] = {}
        self.runs: dict[tuple[str, int], list[dict[str, Any]]] = {}
        self.aggregates: dict[tuple[str, int], dict[str, Any]] = {}
        self.user_email: str | None = None
        self.title: str = ""

    # ------------------------------------------------------------------ helpers

    async def is_cancelled(self) -> bool:
        if await self.redis.get(cancel_key(self.test_id)):
            return True
        async with session_scope() as db:
            status = (
                await db.execute(select(AdTest.status).where(AdTest.id == self.test_id))
            ).scalar_one_or_none()
        return status != "running"

    async def check_cancel(self) -> None:
        if await self.is_cancelled():
            raise Cancelled()

    async def save_state(self, **updates: Any) -> None:
        async with session_scope() as db:
            test = await db.get(AdTest, self.test_id)
            if test is None:
                return
            state = dict(test.pipeline_state or {})
            state.update(updates)
            test.pipeline_state = state
            test.heartbeat_at = now_utc()
            self.state = state

    async def mark_stage(self, stage: str, status: str, detail: dict[str, Any] | None = None) -> None:
        stages = dict(self.state.get("stages", {}))
        entry = dict(stages.get(stage, {}))
        entry["status"] = status
        if status == "running":
            entry["started_at"] = datetime.now(UTC).isoformat()
        if status == "done":
            entry["finished_at"] = datetime.now(UTC).isoformat()
        if detail:
            entry["detail"] = detail
        stages[stage] = entry
        await self.save_state(stages=stages)
        async with session_scope() as db:
            test = await db.get(AdTest, self.test_id)
            if test is not None and test.status == "running":
                test.stage = stage
                test.progress_pct = STAGE_PCT[stage][0] if status == "running" else STAGE_PCT[stage][1]

    def stage_done(self, stage: str) -> bool:
        return (self.state.get("stages", {}).get(stage, {}) or {}).get("status") == "done"

    async def set_progress(self, pct: int) -> None:
        async with session_scope() as db:
            test = await db.get(AdTest, self.test_id)
            if test is not None and test.status == "running":
                test.progress_pct = int(pct)
                test.heartbeat_at = now_utc()

    def combos(self) -> list[tuple[str, int]]:
        assert self.cfg is not None
        n_aud = max(1, min(len(self.cfg.test.audiences), self.cfg.test.tier.max_audiences))
        return [(sel.code, a) for sel in self.cfg.test.platforms for a in range(n_aud)]

    # ------------------------------------------------------------------ stage 1: prepare

    async def prepare(self) -> None:
        await self.mark_stage("prepare", "running")
        await self.publisher.stage("prepare", 1, True)
        async with session_scope() as db:
            test = await db.get(AdTest, self.test_id)
            if test is None:
                raise ApiError(ErrorCode.not_found, "Test vanished")
            user = await db.get(User, test.user_id)
            self.user_email = user.email if user else None
            self.title = test.title
            self.caption = str((test.ad_copy or {}).get("caption") or "")
            assets = list(
                (
                    await db.execute(
                        select(AdAsset)
                        .where(AdAsset.ad_test_id == test.id, AdAsset.kind.in_(["image", "video"]))
                        .order_by(AdAsset.created_at)
                    )
                )
                .scalars()
                .all()
            )
            self.assets = assets
            frozen_inputs = self.state.get("frozen_inputs")
            profile_snapshot = dict(test.profile_snapshot or {})
            category_code = profile_snapshot.get("_category_code") or "other"
            profile = {k: v for k, v in profile_snapshot.items() if not k.startswith("_")}
            budget_usd = None
            if test.budget_minor is not None:
                if test.currency == "USD":
                    budget_usd = test.budget_minor / 100.0
                else:
                    rate = await fx.get_rate(db, test.currency)
                    units = fx.minor_units(test.currency)
                    budget_usd = (
                        (test.budget_minor / units) / float(rate.rate_per_usd)
                        if rate
                        else test.budget_minor / 100.0
                    )
            test_dict = {
                "id": str(test.id),
                "title": test.title,
                "post_type": test.post_type,
                "goal": test.goal,
                "budget_usd": budget_usd,
                "schedule": test.schedule,
                "platforms": test.platforms,
                "audiences": test.audiences,
                "ad_copy": test.ad_copy,
            }
            if frozen_inputs is None:
                # freeze the published layers now so a resumed job uses exactly the same settings
                country = await settings_versions.published_country(db, test.country_code)
                category = await settings_versions.published_category(db, category_code)
                platforms = {
                    p["code"]: await settings_versions.published_platform(db, p["code"])
                    for p in test.platforms
                }
                scenarios = await settings_versions.published_scenarios(db)
                weights = await settings_versions.published_weights(db)
                tier = await settings_versions.tier_dict(db, test.tier_code)
                app_settings = await settings_service.get_all(db)
                frozen_inputs = {
                    "country": country,
                    "category": category,
                    "platforms": platforms,
                    "scenarios": scenarios,
                    "weights": weights,
                    "tier": tier,
                    "settings": app_settings,
                    "test": test_dict,
                    "profile": profile,
                    "frozen_at": datetime.now(UTC).isoformat(),
                }
            self.cfg = resolve(
                country=frozen_inputs["country"],
                platforms=frozen_inputs["platforms"],
                category=frozen_inputs["category"],
                scenarios=frozen_inputs["scenarios"],
                weights=frozen_inputs["weights"],
                test=frozen_inputs["test"],
                tier=frozen_inputs["tier"],
                profile=frozen_inputs["profile"],
                settings=frozen_inputs["settings"],
            )
            test.settings_versions = self.cfg.versions
            test.platforms = [
                {**p, "settings_version": self.cfg.versions["platforms"].get(p["code"])}
                for p in test.platforms
            ]
        await self.save_state(frozen_inputs=frozen_inputs)
        await self.publisher.stage("prepare", 3, True)
        # media: images and video frames / audio
        st = storage.get_storage()
        self.images = []
        video = next((a for a in self.assets if a.kind == "video"), None)
        if video is not None:
            data = await st.get(video.storage_key)
            ext = video.storage_key.rsplit(".", 1)[-1]
            loop = asyncio.get_running_loop()
            frames = await loop.run_in_executor(
                None, media.extract_frames, data, ext, float(video.duration_s or 8.0), 12
            )
            async with session_scope() as db:
                await db.execute(delete(AdAsset).where(AdAsset.parent_asset_id == video.id))
                for i, (t, jpeg) in enumerate(frames):
                    key = storage.frame_key(str(self.test_id), str(video.id), i)
                    await st.put(key, jpeg, "image/jpeg")
                    db.add(
                        AdAsset(
                            ad_test_id=self.test_id,
                            kind="frame",
                            storage_key=key,
                            mime="image/jpeg",
                            size_bytes=len(jpeg),
                            sha256=_sha(jpeg),
                            meta={"t": t},
                            parent_asset_id=video.id,
                        )
                    )
                self.images = [jpeg for _, jpeg in frames][:16]
                audio = await loop.run_in_executor(None, media.extract_audio, data, ext)
                if audio:
                    akey = storage.audio_key(str(self.test_id), str(video.id))
                    await st.put(akey, audio, "audio/mpeg")
                    db.add(
                        AdAsset(
                            ad_test_id=self.test_id,
                            kind="audio",
                            storage_key=akey,
                            mime="audio/mpeg",
                            size_bytes=len(audio),
                            sha256=_sha(audio),
                            meta={},
                            parent_asset_id=video.id,
                        )
                    )
            if audio and not self.state.get("transcript"):
                self.transcript = await self.client.transcribe(stage="prepare", audio=audio)
                await self.save_state(transcript=self.transcript)
            else:
                self.transcript = self.state.get("transcript", "") or ""
        else:
            for a in self.assets[:4]:
                self.images.append(await st.get(a.storage_key))
        await self.mark_stage(
            "prepare",
            "done",
            {
                "assets": len(self.assets),
                "frames": len(self.images) if video else 0,
                "transcript_chars": len(self.transcript),
            },
        )

    # ------------------------------------------------------------------ stage 2: analyze_ad

    async def analyze_ad(self) -> None:
        assert self.cfg is not None
        await self.mark_stage("analyze_ad", "running")
        await self.publisher.stage("analyze_ad", 6, True)
        async with session_scope() as db:
            existing = await db.get(AdAnalysis, self.test_id)
            if existing is not None and self.stage_done("analyze_ad"):
                self.ad = AdFeatures.from_dict(existing.features)
                return
            test = await db.get(AdTest, self.test_id)
            copy = test.ad_copy or {}
        self.client.ensure_configured()
        await self.client.check_budgets(force_daily=True)
        features, version = await llm_tasks.analyze_ad(
            self.client,
            self.cfg,
            caption=str(copy.get("caption") or ""),
            headline=str(copy.get("headline") or ""),
            cta=str(copy.get("cta") or "learn_more"),
            assets=[
                {
                    "kind": a.kind,
                    "width": a.width,
                    "height": a.height,
                    "duration_s": a.duration_s,
                    "sha256": a.sha256,
                }
                for a in self.assets
            ],
            images=self.images,
            transcript=self.transcript,
        )
        self.ad = AdFeatures.from_dict(features)
        async with session_scope() as db:
            row = await db.get(AdAnalysis, self.test_id)
            if row is None:
                row = AdAnalysis(ad_test_id=self.test_id)
                db.add(row)
            row.features = features
            row.description = features.get("description", "")
            row.caption_language = features.get("caption_language")
            row.caption_english = features.get("caption_english")
            row.transcript = self.transcript
            row.model = self.client.model_for("smart")
            row.prompt_version = version
        await self.mark_stage(
            "analyze_ad",
            "done",
            {
                "caption_language": self.ad.caption_language,
                "hook_strength": self.ad.hook_strength,
                "offer_visible_at_s": self.ad.offer_visible_at_s,
            },
        )

    # ------------------------------------------------------------------ stages 3-4: population + archetypes

    async def population_and_archetypes(self) -> None:
        assert self.cfg is not None
        await self.mark_stage("population", "running")
        await self.publisher.stage("population", 12, True)
        combos = self.combos()
        loop = asyncio.get_running_loop()
        for i, (platform_code, aud) in enumerate(combos):
            await self.check_cancel()
            audience = (
                self.cfg.test.audiences[aud]
                if aud < len(self.cfg.test.audiences)
                else {"name": "Main audience", "targeting": {}}
            )
            seed = population_seed(self.cfg.test.test_id, platform_code, aud)
            pop = await loop.run_in_executor(
                None, build_population, self.cfg, platform_code, audience, self.cfg.test.tier.agents, seed
            )
            self.populations[(platform_code, aud)] = pop
            await self.publisher.stage("population", 12 + int(3 * (i + 1) / len(combos)), True)
        await self.mark_stage(
            "population", "done", {"agents": self.cfg.test.tier.agents, "combos": len(combos)}
        )
        await self.mark_stage("archetypes", "running")
        await self.publisher.stage("archetypes", 15, True)
        for i, (platform_code, aud) in enumerate(combos):
            await self.check_cancel()
            pop = self.populations[(platform_code, aud)]
            seed = population_seed(self.cfg.test.test_id, platform_code, aud)
            table = await loop.run_in_executor(
                None, build_archetypes, pop, self.cfg.test.tier.archetypes, seed
            )
            self.tables[(platform_code, aud)] = table
            await self.publisher.stage("archetypes", 15 + int(3 * (i + 1) / len(combos)), True)
        # persist archetype rows (once) so reactions can be attached and resumed
        async with session_scope() as db:
            count = (
                await db.execute(
                    select(func.count()).select_from(Archetype).where(Archetype.ad_test_id == self.test_id)
                )
            ).scalar_one()
            if not count:
                for (platform_code, aud), table in self.tables.items():
                    for sc in self.cfg.scenarios:
                        for idx, profile in enumerate(table.profiles):
                            db.add(
                                Archetype(
                                    ad_test_id=self.test_id,
                                    platform_code=platform_code,
                                    audience_idx=aud,
                                    scenario=sc.code,
                                    idx=idx,
                                    profile=profile,
                                    size=int(table.sizes[idx]),
                                )
                            )
        await self.mark_stage(
            "archetypes", "done", {"archetypes": {f"{p}:{a}": t.k for (p, a), t in self.tables.items()}}
        )

    # ------------------------------------------------------------------ stage 5: react

    async def react(self) -> None:
        assert self.cfg is not None and self.ad is not None
        await self.mark_stage("react", "running")
        combos = self.combos()
        total_jobs = len(combos) * len(self.cfg.scenarios)
        done_jobs = 0
        await self.publisher.stage("react", 18, True)
        for platform_code, aud in combos:
            table = self.tables[(platform_code, aud)]
            placement = next(
                (
                    p.placements[0]
                    for p in self.cfg.test.platforms
                    if p.code == platform_code and p.placements
                ),
                "feed",
            )
            for sc in self.cfg.scenarios:
                await self.check_cancel()
                async with session_scope() as db:
                    rows = (
                        await db.execute(
                            select(Archetype.id, Archetype.idx, ArchetypeReaction.reaction)
                            .join(
                                ArchetypeReaction,
                                ArchetypeReaction.archetype_id == Archetype.id,
                                isouter=True,
                            )
                            .where(
                                Archetype.ad_test_id == self.test_id,
                                Archetype.platform_code == platform_code,
                                Archetype.audience_idx == aud,
                                Archetype.scenario == sc.code,
                            )
                        )
                    ).all()
                arche_ids = {int(idx): aid for aid, idx, _ in rows}
                existing = {int(idx): r for _, idx, r in rows if r}
                pop = self.populations[(platform_code, aud)]

                async def on_reaction(
                    idx: int,
                    r: dict[str, Any],
                    _pc: str = platform_code,
                    _t: ArchetypeTable = table,
                    _pop: Population = pop,
                ) -> None:
                    if r.get("comment"):
                        prof = _t.profiles[idx]
                        await self.publisher.comment(
                            prof.get("label", f"archetype {idx}"),
                            str(r["comment"]),
                            r.get("comment_topic"),
                            _pc,
                            prof.get("language_group", "en"),
                        )

                reactions, version, fallbacks = await llm_tasks.react_archetypes(
                    self.client,
                    self.cfg,
                    self.ad,
                    table,
                    platform_code,
                    placement,
                    sc,
                    self.caption,
                    existing=existing,
                    on_reaction=on_reaction,
                    should_cancel=self.is_cancelled,
                )
                await self.check_cancel()
                # persist new reactions
                async with session_scope() as db:
                    for idx, r in enumerate(reactions):
                        if r is None or idx in existing:
                            continue
                        aid = arche_ids.get(idx)
                        if aid is None:
                            continue
                        from_idx = fallbacks.get(idx)
                        db.add(
                            ArchetypeReaction(
                                archetype_id=aid,
                                reaction=r,
                                comment=r.get("comment"),
                                reason=r.get("reason"),
                                model="engine",
                                prompt_version=version,
                                fallback_from=arche_ids.get(from_idx) if from_idx is not None else None,
                            )
                        )
                self.reactions[(platform_code, aud, sc.code)] = reactions
                self.priors[(platform_code, aud, sc.code)] = priors_from_reactions(reactions, table.k)
                done_jobs += 1
                pct = 18 + int(32 * done_jobs / max(1, total_jobs))
                await self.publisher.stage(
                    "react",
                    pct,
                    True,
                    extra={"platform": platform_code, "scenario": sc.code, "audience_idx": aud},
                )
                await self.set_progress(pct)
        alerts = {}
        for key, reactions in self.reactions.items():
            alert = llm_tasks.variety_alert(
                reactions, float((self.cfg.settings.get("limits") or {}).get("positive_share_alert", 0.6))
            )
            if alert:
                alerts[":".join(str(k) for k in key)] = alert
        await self.mark_stage("react", "done", {"calls": self.client.totals.calls, "alerts": alerts})

    # ------------------------------------------------------------------ stage 6: simulate

    async def simulate(self) -> None:
        assert self.cfg is not None and self.ad is not None
        await self.mark_stage("simulate", "running")
        # the cancel window closes here
        async with session_scope() as db:
            test = await db.get(AdTest, self.test_id)
            if test is not None:
                test.cancel_window_open = False
        await self.publisher.stage("simulate", 50, False)
        combos = self.combos()
        target = self.cfg.test.tier.runs_target
        loop = asyncio.get_running_loop()
        for ci, (platform_code, aud) in enumerate(combos):
            await self.check_cancel()
            pop = self.populations[(platform_code, aud)]
            priors_by_sc = {sc.code: self.priors[(platform_code, aud, sc.code)] for sc in self.cfg.scenarios}
            # reference ad: same ad with average creative quality, scored on the same audience and seeds
            ref_ad = reference_ad(self.ad)
            ref_table = self.tables[(platform_code, aud)]
            ref_placement = next(
                (
                    p.placements[0]
                    for p in self.cfg.test.platforms
                    if p.code == platform_code and p.placements
                ),
                "feed",
            )
            ref_priors_by_sc = {}
            for sc in self.cfg.scenarios:
                ref_reactions, _ref_version, _ref_fallbacks = await llm_tasks.react_archetypes(
                    self.client,
                    self.cfg,
                    ref_ad,
                    ref_table,
                    platform_code,
                    ref_placement,
                    sc,
                    self.caption,
                )
                ref_priors_by_sc[sc.code] = priors_from_reactions(ref_reactions, ref_table.k)
            share = next((p.budget_share for p in self.cfg.test.platforms if p.code == platform_code), 100.0)
            bias = await loop.run_in_executor(
                None,
                lambda: calibrate_bias(
                    self.cfg, ref_ad, pop, ref_priors_by_sc, platform_code, aud, share
                ),
            )
            async with session_scope() as db:
                existing_rows = (
                    (
                        await db.execute(
                            select(RunResult)
                            .where(
                                RunResult.ad_test_id == self.test_id,
                                RunResult.platform_code == platform_code,
                                RunResult.audience_idx == aud,
                            )
                            .order_by(RunResult.run_no)
                        )
                    )
                    .scalars()
                    .all()
                )
                existing = [
                    dict(r.metrics, run_no=r.run_no, score=r.score, audience_idx=aud) for r in existing_rows
                ]
            pending: list[dict[str, Any]] = []

            def on_batch(batch: list[dict[str, Any]], all_runs: list[dict[str, Any]], finished: bool) -> bool:
                pending.extend(batch)
                return True

            # run the numeric loop in a thread in chunks so we can publish events and check cancel
            runs = list(existing)
            while len(runs) < target:
                pending.clear()
                chunk_target = min(target, len(runs) + 5)
                runs = await loop.run_in_executor(
                    None,
                    lambda: simulate_platform_audience(
                        self.cfg,
                        self.ad,
                        pop,
                        priors_by_sc,
                        platform_code,
                        aud,
                        share,
                        on_batch=on_batch,
                        runs_target=chunk_target,
                        min_runs=self.cfg.test.tier.min_runs,
                        existing_runs=runs,
                        ref_ad=ref_ad,
                        ref_priors_by_scenario=ref_priors_by_sc,
                        bias=bias,
                    ),
                )
                async with session_scope() as db:
                    for m in pending:
                        db.add(
                            RunResult(
                                ad_test_id=self.test_id,
                                platform_code=platform_code,
                                audience_idx=aud,
                                run_no=int(m["run_no"]),
                                scenario=m["scenario"],
                                seed=int(m["seed"]),
                                metrics=m,
                                score=m.get("score"),
                            )
                        )
                agg_est = run_batch_estimate(runs, self.cfg.test.goal)
                funnel = _funnel_from_runs(runs)
                frac = (ci + min(1.0, len(runs) / target)) / len(combos)
                pct = 50 + int(35 * frac)
                await self.publisher.run_batch(
                    pct=pct,
                    runs_done=len(runs),
                    runs_target=target,
                    batch=pending,
                    estimate=agg_est,
                    funnel=funnel,
                    confidence=confidence_label(len(runs), self.cfg.test.tier.min_runs, target),
                    platform=platform_code,
                    audience_idx=aud,
                )
                await self.set_progress(pct)
                # stopping rule (min runs, then <5% change of the goal metric over the last 10 runs)
                if should_stop(runs, self.cfg.test.tier.min_runs) or len(runs) >= target:
                    break
                if await self.is_cancelled():
                    raise Cancelled()
            self.runs[(platform_code, aud)] = runs
            self.aggregates[(platform_code, aud)] = summarize(runs, self.cfg.test.goal)
        await self.mark_stage(
            "simulate", "done", {"runs": {f"{p}:{a}": len(r) for (p, a), r in self.runs.items()}}
        )

    # ------------------------------------------------------------------ stage 7: explain

    async def explain(self) -> dict[str, Any]:
        assert self.cfg is not None and self.ad is not None
        await self.mark_stage("explain", "running")
        await self.publisher.stage("explain", 86, False)
        builder = EvidenceBuilder()
        combos = self.combos()
        for platform_code, aud in combos:
            priors = self.priors[(platform_code, aud, self.cfg.scenarios[0].code)]
            build_evidence(
                self.aggregates[(platform_code, aud)],
                priors,
                self.cfg,
                platform_code,
                aud,
                self.ad.to_dict(),
                builder,
            )
        evidence = builder.items
        # comments from reactions, classified in batches, counted per language group
        comments: list[dict[str, Any]] = []
        for (platform_code, aud, sc_code), reactions in self.reactions.items():
            table = self.tables[(platform_code, aud)]
            for idx, r in enumerate(reactions):
                if r and r.get("comment"):
                    prof = table.profiles[idx]
                    comments.append(
                        {
                            "archetype": prof.get("label", f"archetype {idx}"),
                            "text": str(r["comment"]),
                            "topic": r.get("comment_topic"),
                            "sentiment": float(r.get("sentiment", 0.0)),
                            "language_group": prof.get("language_group", "en"),
                            "platform": platform_code,
                            "scenario": sc_code,
                            "audience_idx": aud,
                            "size": int(prof.get("size", 0)),
                        }
                    )
        await self.check_cancel()
        await self.publisher.stage("explain", 89, False)
        comments.sort(key=lambda c: -c["size"])
        await self.publisher.stage("explain", 92, False)
        goal_metric = self.aggregates[combos[0]]["goal_metric"]
        example = [c["text"] for c in comments[:20]]
        reasons, rejected, reasons_version = await llm_tasks.write_reasons(
            self.client, self.cfg, evidence, example, goal_metric
        )
        report = self.build_report(evidence, reasons, comments)
        report["meta"] = {"reasons_prompt_version": reasons_version, "rejected_reasons": rejected}
        await self.mark_stage(
            "explain",
            "done",
            {
                "evidence": len(evidence),
                "reasons": len(reasons),
                "rejected": len(rejected),
                "comments": len(comments),
            },
        )
        return report

    def build_report(
        self, evidence: list[dict[str, Any]], reasons: list[dict[str, Any]], comments: list[dict[str, Any]]
    ) -> dict[str, Any]:
        assert self.cfg is not None and self.ad is not None
        combos = self.combos()
        shares = {p.code: p.budget_share for p in self.cfg.test.platforms}
        platforms_out = []
        per_platform_agg: dict[str, dict[str, Any]] = {}
        audiences_out = []
        for platform_code, aud in combos:
            agg = self.aggregates[(platform_code, aud)]
            comps = score_components(
                {
                    "rates": {k: v["p50"] for k, v in agg["rates"].items()},
                    "sentiment": agg["sentiment"]["p50"],
                },
                self.cfg.test.goal,
                self.cfg.platforms[platform_code].benchmarks,
                self.cfg.weights.score_by_goal,
            )
            entry = {
                "code": platform_code,
                "name": self.cfg.platforms[platform_code].name,
                "status": self.cfg.platforms[platform_code].status,
                "audience_idx": aud,
                "audience_name": (
                    self.cfg.test.audiences[aud].get("name")
                    if aud < len(self.cfg.test.audiences)
                    else "Main audience"
                ),
                "budget_share": shares.get(platform_code),
                "runs": agg["runs"],
                "score": agg["score"],
                "score_components": comps,
                "goal_value": agg["goal_value"],
                "goal_rate": agg["goal_rate"],
                "rates": agg["rates"],
                "counts": agg["counts"],
                "funnel": agg["funnel"],
                "benchmarks": self.cfg.platforms[platform_code].benchmarks,
                "scenarios": agg["scenarios"],
                "blockers": agg["blockers"],
                "comment_topics": agg["comment_topics"],
                "dropoff": agg["dropoff"],
                "fatigue": agg["fatigue"],
                "taste": agg["taste"],
                "timing": agg["timing"],
                "segments": agg["segments"],
            }
            platforms_out.append(entry)
            if aud == 0:
                per_platform_agg[platform_code] = agg
        overall = combine_platforms(per_platform_agg, shares)
        n_aud = max(1, min(len(self.cfg.test.audiences), self.cfg.test.tier.max_audiences))
        if n_aud > 1:
            for aud in range(n_aud):
                aggs = {pc: self.aggregates[(pc, aud)] for pc, a in combos if a == aud}
                comb = combine_platforms(aggs, shares)
                audiences_out.append(
                    {
                        "audience_idx": aud,
                        "name": self.cfg.test.audiences[aud].get("name", f"Audience {aud + 1}"),
                        "targeting": self.cfg.test.audiences[aud].get("targeting", {}),
                        "score": comb.get("score"),
                        "goal_value": comb.get("goal_value"),
                        "rates": comb.get("rates"),
                        "counts": comb.get("counts"),
                        "evidence_ids": [e["id"] for e in evidence if e.get("audience_idx") == aud],
                    }
                )
        else:
            audiences_out.append(
                {
                    "audience_idx": 0,
                    "name": (
                        self.cfg.test.audiences[0].get("name") if self.cfg.test.audiences else "Main audience"
                    ),
                    "targeting": (
                        self.cfg.test.audiences[0].get("targeting", {}) if self.cfg.test.audiences else {}
                    ),
                    "score": overall.get("score"),
                    "goal_value": overall.get("goal_value"),
                    "rates": overall.get("rates"),
                    "counts": overall.get("counts"),
                    "evidence_ids": [e["id"] for e in evidence],
                }
            )
        goal_metric = self.aggregates[combos[0]]["goal_metric"]
        goal_rate_key = self.aggregates[combos[0]]["goal_rate_key"]
        score = overall.get("score", {}).get("p50") if overall.get("score") else None
        # language groups: reactions and comments per group
        lang_groups: dict[str, dict[str, Any]] = {}
        for platform_code, aud in combos:
            agg = self.aggregates[(platform_code, aud)]
            for code, row in (agg.get("segments", {}).get("language_group") or {}).items():
                g = lang_groups.setdefault(
                    code,
                    {
                        "code": code,
                        "name": _lang_name(self.cfg, code),
                        "seen": 0.0,
                        "stopped": 0.0,
                        "clicked": 0.0,
                        "commented": 0.0,
                        "comments": 0,
                        "reactions_positive": 0,
                        "reactions_negative": 0,
                    },
                )
                for k in ("seen", "stopped", "clicked", "commented"):
                    g[k] += float(row.get(k, 0))
        for c in comments:
            g = lang_groups.setdefault(
                c["language_group"],
                {
                    "code": c["language_group"],
                    "name": _lang_name(self.cfg, c["language_group"]),
                    "seen": 0.0,
                    "stopped": 0.0,
                    "clicked": 0.0,
                    "commented": 0.0,
                    "comments": 0,
                    "reactions_positive": 0,
                    "reactions_negative": 0,
                },
            )
            g["comments"] += 1
        for (platform_code, aud, _sc), reactions in self.reactions.items():
            table = self.tables[(platform_code, aud)]
            for idx, r in enumerate(reactions):
                if not r:
                    continue
                code = table.profiles[idx].get("language_group", "en")
                g = lang_groups.setdefault(
                    code,
                    {
                        "code": code,
                        "name": _lang_name(self.cfg, code),
                        "seen": 0.0,
                        "stopped": 0.0,
                        "clicked": 0.0,
                        "commented": 0.0,
                        "comments": 0,
                        "reactions_positive": 0,
                        "reactions_negative": 0,
                    },
                )
                if float(r.get("sentiment", 0)) > 0.2:
                    g["reactions_positive"] += 1
                elif float(r.get("sentiment", 0)) < -0.2:
                    g["reactions_negative"] += 1
        for g in lang_groups.values():
            g["stop_rate"] = round(g["stopped"] / g["seen"], 4) if g["seen"] else 0.0
            g["ctr"] = round(g["clicked"] / g["seen"], 4) if g["seen"] else 0.0
            for k in ("seen", "stopped", "clicked", "commented"):
                g[k] = int(round(g[k]))
        first = self.aggregates[combos[0]]
        ad_image, caption_stats = self._impression_sections()
        summary = {
            "ad_image": ad_image,
            "caption": caption_stats,
            "score": score,
            "score_range": overall.get("score"),
            "goal": self.cfg.test.goal,
            "goal_metric": goal_metric,
            "goal_rate_key": goal_rate_key,
            "goal_value": overall.get("goal_value"),
            "goal_rate": overall["rates"].get(goal_rate_key)
            if overall.get("rates")
            else first.get("goal_rate"),
            "rates": overall.get("rates"),
            "counts": overall.get("counts"),
            "sentiment": overall.get("sentiment"),
            "population_per_platform": first.get("population"),
            "scale": first.get("scale"),
            "runs_total": sum(a["runs"] for a in self.aggregates.values()),
            "ad_features": self.ad.to_dict(),
            "caption_language": self.ad.caption_language,
            "caption_english": self.ad.caption_english,
            "scenarios": [s.to_dict() for s in self.cfg.scenarios],
            "cost_usd": round(self.client.totals.cost_usd, 4),
            "llm_calls": self.client.totals.calls,
            "post_type": self.cfg.test.post_type,
            "budget_usd": self.cfg.test.budget_usd,
            "variety_alerts": (self.state.get("stages", {}).get("react", {}).get("detail", {}) or {}).get(
                "alerts", {}
            ),
        }
        headline = {
            "metric": goal_metric,
            "label": _metric_label(goal_metric),
            "value": overall.get("goal_value"),
            "rate_key": goal_rate_key,
            "rate": summary["goal_rate"],
            "estimated_people": {
                k: int(round(v * first.get("scale", 1.0)))
                for k, v in (overall.get("goal_value") or {}).items()
            },
        }
        funnel = (
            first["funnel"]
            if len(combos) == 1
            else _sum_funnels([self.aggregates[(pc, 0)]["funnel"] for pc, a in combos if a == 0])
        )
        segments = {"per_platform": {f"{pc}:{a}": self.aggregates[(pc, a)]["segments"] for pc, a in combos}}
        brand = {
            f"{pc}:{a}": self.aggregates[(pc, a)]["segments"].get("brand_relationship", {})
            for pc, a in combos
        }
        brand["awareness_inputs"] = {
            k: self.cfg.profile.get(k) for k in ("followers", "review_count", "rating", "months_in_business")
        }
        timing = {
            f"{pc}:{a}": {
                "timing": self.aggregates[(pc, a)]["timing"],
                "fatigue": self.aggregates[(pc, a)]["fatigue"],
                "dropoff": self.aggregates[(pc, a)]["dropoff"],
            }
            for pc, a in combos
        }
        return {
            "summary": summary,
            "headline_metric": headline,
            "funnel": funnel,
            "segments": segments,
            "brand_relationship": brand,
            "comments": [{k: v for k, v in c.items() if k != "size"} for c in comments[:200]],
            "timing": timing,
            "reasons": reasons,
            "evidence": evidence,
            "audiences": audiences_out,
            "platforms": platforms_out,
            "language_groups": sorted(lang_groups.values(), key=lambda g: -g["seen"]),
        }

    def _impression_sections(self) -> tuple[dict[str, Any], dict[str, Any]]:
        """Impressed vs. not impressed by the image, caption read vs. ignored (archetype-size weighted),
        with the most common first impressions as the stated reasons."""
        impressed = not_impressed = read = ignored = 0.0
        impressions: dict[str, float] = {}
        for (platform_code, aud, _sc), reactions in self.reactions.items():
            table = self.tables[(platform_code, aud)]
            for idx, r in enumerate(reactions):
                if not r:
                    continue
                w = float(table.profiles[idx].get("size", 1))
                if r.get("image_impressed"):
                    impressed += w
                else:
                    not_impressed += w
                if r.get("caption_read"):
                    read += w
                else:
                    ignored += w
                fi = str(r.get("first_impression") or "").strip()
                if fi:
                    impressions[fi] = impressions.get(fi, 0.0) + w
        total_img = impressed + not_impressed or 1.0
        total_cap = read + ignored or 1.0
        top = sorted(impressions.items(), key=lambda kv: -kv[1])[:6]
        ad_image = {
            "impressed_share": round(impressed / total_img, 4),
            "not_impressed_share": round(not_impressed / total_img, 4),
            "top_first_impressions": [{"text": t, "weight": round(w / total_img, 4)} for t, w in top],
        }
        caption_stats = {
            "read_share": round(read / total_cap, 4),
            "ignored_share": round(ignored / total_cap, 4),
            "language": self.ad.caption_language if self.ad else None,
            "english": self.ad.caption_english if self.ad else None,
        }
        return ad_image, caption_stats

    # ------------------------------------------------------------------ stage 8: export

    async def export(self, report: dict[str, Any]) -> float | None:
        assert self.cfg is not None
        await self.mark_stage("export", "running")
        await self.publisher.stage("export", 97, False)
        note = str(
            self.cfg.settings.get("report_note")
            or "Results come from a simulation of virtual audiences. They show likely reactions, not guaranteed outcomes."
        )
        score = report["summary"].get("score")
        async with session_scope() as db:
            row = await db.get(Report, self.test_id)
            if row is None:
                row = Report(ad_test_id=self.test_id)
                db.add(row)
            row.summary = _jsonable(
                {
                    **report["summary"],
                    "headline_metric": report["headline_metric"],
                    "meta": report.get("meta", {}),
                }
            )
            row.funnel = _jsonable(report["funnel"])
            row.segments = _jsonable(report["segments"])
            row.brand_relationship = _jsonable(report["brand_relationship"])
            row.comments = _jsonable(report["comments"])
            row.timing = _jsonable(report["timing"])
            row.reasons = _jsonable(report["reasons"])
            row.evidence = _jsonable(report["evidence"])
            row.audiences = _jsonable(report["audiences"])
            row.platforms = _jsonable(report["platforms"])
            row.language_groups = _jsonable(report["language_groups"])
            row.version = "1"
            row.note = note
        pdf_bytes = await asyncio.get_running_loop().run_in_executor(
            None,
            report_pdf.render_pdf,
            {
                "title": self.title,
                "test_id": str(self.test_id),
                "goal": self.cfg.test.goal,
                "post_type": self.cfg.test.post_type,
                "country": self.cfg.country.name,
                "note": note,
                "settings_versions": self.cfg.versions,
                "engine_version": self.settings.ENGINE_VERSION,
                **_jsonable(report),
            },
        )
        key = storage.report_pdf_key(str(self.test_id))
        await storage.get_storage().put(key, pdf_bytes, "application/pdf")
        async with session_scope() as db:
            row = await db.get(Report, self.test_id)
            if row is not None:
                row.pdf_key = key
        await self.mark_stage("export", "done", {"pdf_bytes": len(pdf_bytes)})
        return score

    # ------------------------------------------------------------------ run

    async def run(self) -> dict[str, Any]:
        started = time.perf_counter()
        async with session_scope() as db:
            res = await db.execute(select(AdTest).where(AdTest.id == self.test_id).with_for_update())
            test = res.scalar_one_or_none()
            if test is None:
                return {"ok": False, "reason": "not_found"}
            if test.status == "queued":
                test.status = "running"
                test.started_at = now_utc()
                test.heartbeat_at = now_utc()
                test.cancel_window_open = True
                test.error = None
            elif test.status == "running":
                test.heartbeat_at = now_utc()  # retry / resume
            else:
                return {"ok": False, "reason": f"status {test.status}"}
            self.state = dict(test.pipeline_state or {})
            self.title = test.title
        await self.redis.delete(cancel_key(self.test_id))
        try:
            await self.prepare()
            await self.check_cancel()
            await self.analyze_ad()
            await self.check_cancel()
            await self.population_and_archetypes()
            await self.check_cancel()
            await self.react()
            await self.check_cancel()
            await self.simulate()
            report = await self.explain()
            score = await self.export(report)
            async with session_scope() as db:
                res = await db.execute(select(AdTest).where(AdTest.id == self.test_id).with_for_update())
                test = res.scalar_one()
                if test.status == "running":
                    test.status = "completed"
                    test.finished_at = now_utc()
                    test.progress_pct = 100
                    test.score = score
                    test.stage = "export"
                    test.cancel_window_open = False
                    test.rerun_available = False
                await audit_service.log(
                    db,
                    actor_id=None,
                    action="test.completed",
                    entity="ad_test",
                    entity_id=self.test_id,
                    data={
                        "score": score,
                        "cost_usd": self.client.totals.cost_usd,
                        "llm_calls": self.client.totals.calls,
                        "elapsed_s": round(time.perf_counter() - started, 1),
                    },
                )
            await self.publisher.completed(score, f"/tests/{self.test_id}/report")
            if self.user_email:
                await email_service.send_report_ready(self.user_email, self.title, str(self.test_id), score)
            return {
                "ok": True,
                "score": score,
                "cost_usd": self.client.totals.cost_usd,
                "elapsed_s": round(time.perf_counter() - started, 1),
            }
        except Cancelled:
            async with session_scope() as db:
                test = await db.get(AdTest, self.test_id)
                free = bool(test.free_restart_available) if test else False
                if test is not None and test.status == "running":
                    # cancelled by status change elsewhere (e.g. queue cancel); keep as draft
                    test.status = "draft"
                    test.cancel_window_open = False
                await audit_service.log(
                    db,
                    actor_id=None,
                    action="test.cancelled_by_worker",
                    entity="ad_test",
                    entity_id=self.test_id,
                    data={"cost_usd": self.client.totals.cost_usd, "llm_calls": self.client.totals.calls},
                )
            await self.publisher.cancelled(free)
            return {"ok": False, "reason": "cancelled", "cost_usd": self.client.totals.cost_usd}
        except ApiError as exc:
            await self._fail(exc.code.value, exc.message, exc.details)
            raise
        except Exception as exc:  # noqa: BLE001
            log.exception("run_test failed test_id=%s", self.test_id)
            await self._fail("engine_error", f"{exc.__class__.__name__}: {exc}"[:500], None)
            raise

    async def _fail(self, code: str, message: str, details: Any) -> None:
        async with session_scope() as db:
            res = await db.execute(select(AdTest).where(AdTest.id == self.test_id).with_for_update())
            test = res.scalar_one_or_none()
            if test is None:
                return
            if test.status == "running":
                test.status = "failed"
                test.finished_at = now_utc()
                test.cancel_window_open = False
                test.rerun_available = True
                test.error = {
                    "code": code,
                    "message": message,
                    "details": _jsonable(details),
                    "stage": test.stage,
                    "cost_usd": self.client.totals.cost_usd,
                }
            await audit_service.log(
                db,
                actor_id=None,
                action="test.failed",
                entity="ad_test",
                entity_id=self.test_id,
                data={"code": code, "message": message, "stage": test.stage},
            )
        await self.publisher.failed(code, message, True)
        if self.user_email:
            await email_service.send_test_failed(self.user_email, self.title, str(self.test_id))


# --------------------------------------------------------------------------- helpers


def _sha(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _lang_name(cfg: FrozenConfig, code: str) -> str:
    for g in cfg.country.language_groups:
        if g.code == code:
            return g.name
    return code


def _metric_label(metric: str) -> str:
    return {
        "buys": "Purchases",
        "messages": "Chats started",
        "clicks": "Link clicks",
        "noticed": "People who noticed",
        "engagements": "Reactions, comments, shares and saves",
    }.get(metric, metric)


def _funnel_from_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    if not runs:
        return {}
    keys = ("seen", "skipped", "stopped", "reacted", "commented", "clicked", "messaged", "bought")
    return {k: int(np.median([r["counts"].get(k, 0) for r in runs])) for k in keys}


def _sum_funnels(funnels: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for f in funnels:
        for k, v in f.items():
            if isinstance(v, dict):
                out.setdefault(k, {})
                for kk, vv in v.items():
                    out[k][kk] = out[k].get(kk, 0) + vv
            elif isinstance(v, (int, float)):
                out[k] = out.get(k, 0) + v
    return out


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, float) and (value != value):  # NaN
        return None
    return value


async def run_test(ctx: dict[str, Any], test_id: str) -> dict[str, Any]:
    """Arq entry point (20-minute timeout, 2 tries)."""
    test_id_var.set(str(test_id))
    run = TestRun(uuid.UUID(str(test_id)))
    return await run.run()


async def run_test_inline(test_id: uuid.UUID) -> dict[str, Any]:
    return await TestRun(test_id).run()


async def ensure_llm_ready_or_fail(db: AsyncSession, test_id: uuid.UUID) -> None:
    """Used by the API before enqueueing when a fast failure is preferable (not used by default)."""
    client = LLMClient(test_id=test_id, log_usage=False)
    client.ensure_configured()
