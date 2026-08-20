"""Insert a shared demo account with a three-retro recurrence story.

Re-running deletes only this user (CASCADE) and recreates the same story.
Does not touch other accounts.

  cd apps/api
  python -m app.seed_demo
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.action_draft import ActionDraft
from app.models.action_event import ActionEvent
from app.models.action_item import ActionItem
from app.models.problem import ProblemOccurrence
from app.models.problem_cluster import ProblemCluster
from app.models.retro import Retro
from app.models.user import User
from app.models.weekly_review import WeeklyReview

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo1234"

_CHECKLIST = "发布前检查项经常遗漏"
_NORMALIZED = "release checklist items are skipped before deploy"


def seed_demo(db: Session) -> User:
    """Replace the demo user and recreate the sample story."""
    today = datetime.now(UTC).date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    first_retro_date = today - timedelta(days=42)
    second_retro_date = today - timedelta(days=21)
    latest_retro_date = today

    existing = db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if existing is not None:
        db.delete(existing)
        db.commit()

    user = User(
        id=uuid4(),
        email=DEMO_EMAIL,
        password_hash=hash_password(DEMO_PASSWORD),
        locale="zh-CN",
    )
    db.add(user)
    db.flush()

    cluster = ProblemCluster(
        id=uuid4(),
        user_id=user.id,
        canonical_title="发布清单遗漏",
        category="delivery",
        first_seen_at=_at(first_retro_date),
    )
    db.add(cluster)
    db.flush()

    r1 = _retro(
        user,
        retro_type="sprint",
        title=f"Sprint Retro · {first_retro_date.isoformat()}",
        review_date=first_retro_date,
        created_at=_at(first_retro_date),
        raw_content=(
            "发布当天才发现数据库迁移没有跑。会上有人说："
            "这次又漏了数据库迁移检查，发布清单还是不全。"
        ),
        summary={
            "keep": ["发布当天发现迁移未执行"],
            "decisions": [
                {"decision": "先记问题，下个迭代补清单", "reason": "本轮已无发布窗口"}
            ],
            "risks": [{"risk": "清单缺口会在下次发布再现", "suggestion": "把检查项写入仓库"}],
        },
    )
    r2 = _retro(
        user,
        retro_type="release",
        title=f"Release Review · {second_retro_date.isoformat()}",
        review_date=second_retro_date,
        created_at=_at(second_retro_date),
        raw_content=(
            "第二次发布仍漏了检查项。原文："
            "PR 模板里没有 release checklist，评审过了也能合进主干。"
        ),
        summary={
            "keep": ["同一发布清单问题第二次出现"],
            "decisions": [
                {"decision": "补 PR 模板强制填写检查项", "reason": "人工记清单不可靠"}
            ],
            "risks": [{"risk": "模板仍可被跳过", "suggestion": "后续把检查放进 CI"}],
        },
    )
    r3 = _retro(
        user,
        retro_type="release",
        title=f"Release Review · {latest_retro_date.isoformat()}",
        review_date=latest_retro_date,
        created_at=_at(latest_retro_date),
        raw_content=(
            "第三次出现发布清单遗漏。原文："
            "这次又漏了数据库迁移检查，CI 没有在缺 migration 时拦住合并。"
        ),
        summary={
            "keep": ["发布清单遗漏第三次出现"],
            "decisions": [
                {"decision": "在 CI 校验 migration 与 checklist", "reason": "模板未能阻止漏项"}
            ],
            "risks": [{"risk": "回滚步骤仍靠口头", "suggestion": "补一次回滚演练"}],
        },
    )
    db.add_all([r1, r2, r3])
    db.flush()

    p1 = _problem(user, r1, cluster, match_status="auto_created")
    p2 = _problem(user, r2, cluster, match_status="auto_linked")
    p3 = _problem(user, r3, cluster, match_status="auto_linked")
    db.add_all([p1, p2, p3])
    db.flush()

    d2 = _draft(
        user,
        r2,
        p2,
        title="补 PR 模板，强制填写 release checklist",
        description="在 PR 模板增加迁移与发布检查项，未勾选不得合并。",
        criteria="缺少 checklist 的 PR 无法通过模板检查。",
    )
    d3a = _draft(
        user,
        r3,
        p3,
        title="在 CI 中校验 migration 与 release checklist",
        description="缺 migration 检查时 CI 失败并阻止合并。",
        criteria="测试环境缺少迁移时 CI 正确失败。",
    )
    d3b = _draft(
        user,
        r3,
        p3,
        title="补充 incident 回滚演练",
        description="把回滚步骤写成可执行剧本并演练一次。",
        criteria="演练记录可在复盘中打开。",
    )
    db.add_all([d2, d3a, d3b])
    db.flush()

    a_template = _action(
        user,
        r2,
        p2,
        title=d2.title,
        description=d2.description,
        owner="Alex",
        due_date=second_retro_date + timedelta(days=6),
        criteria=d2.suggested_success_criteria,
        status="verified",
        verified_at=_at(second_retro_date + timedelta(days=6), 9),
        created_at=_at(second_retro_date, 10),
    )
    a_ci = _action(
        user,
        r3,
        p3,
        title=d3a.title,
        description=d3a.description,
        owner="Alex",
        due_date=today,
        criteria=d3a.suggested_success_criteria,
        status="evidence_submitted",
        created_at=_at(latest_retro_date, 10),
    )
    a_rollback = _action(
        user,
        r3,
        p3,
        title=d3b.title,
        description=d3b.description,
        owner="Jordan",
        due_date=week_end,
        criteria=d3b.suggested_success_criteria,
        status="in_progress",
        created_at=_at(latest_retro_date, 11),
    )
    db.add_all([a_template, a_ci, a_rollback])
    db.flush()

    db.add_all(
        [
            _event(
                user,
                a_template,
                "created",
                to_status="open",
                at=_at(second_retro_date, 10),
            ),
            _event(
                user,
                a_template,
                "evidence_submitted",
                from_status="open",
                to_status="evidence_submitted",
                note="已更新 PR 模板并在一次真实 PR 中使用。",
                evidence_text="模板增加 migration / checklist 必填项。",
                evidence_url="https://github.com/example/retroflow/blob/main/.github/PULL_REQUEST_TEMPLATE.md",
                at=_at(second_retro_date + timedelta(days=4), 11),
            ),
            _event(
                user,
                a_template,
                "verified",
                from_status="evidence_submitted",
                to_status="verified",
                note="模板已在主干生效。",
                at=_at(second_retro_date + timedelta(days=6), 9),
            ),
            _event(
                user,
                a_ci,
                "created",
                to_status="open",
                at=_at(latest_retro_date, 10),
            ),
            _event(
                user,
                a_ci,
                "evidence_submitted",
                from_status="in_progress",
                to_status="evidence_submitted",
                note="已新增 migration check，并验证失败路径。",
                evidence_text="测试环境缺少迁移时 CI 正确失败。",
                evidence_url="https://github.com/example/retroflow/actions/runs/1001",
                at=_at(latest_retro_date, 16),
            ),
            _event(
                user,
                a_rollback,
                "created",
                to_status="open",
                at=_at(latest_retro_date, 11),
            ),
            _event(
                user,
                a_rollback,
                "status_changed",
                from_status="open",
                to_status="in_progress",
                note="开始写回滚剧本。",
                at=_at(latest_retro_date, 12),
            ),
        ]
    )

    db.add(
        WeeklyReview(
            id=uuid4(),
            user_id=user.id,
            week_start=week_start,
            week_end=week_end,
            content_markdown=(
                "## 本周完成\n"
                "发布清单相关的 PR 模板已在历史复盘中验收；本周继续推进 CI 校验。\n\n"
                "## 延期与风险\n"
                "- CI migration check 已提交证据，等待验收。\n"
                "- 回滚演练仍在进行，本周到期。\n\n"
                "## 重复问题\n"
                "发布清单遗漏已跨三次复盘出现，模板未能拦住第三次。\n\n"
                "## 下周重点\n"
                "建议：先验收 CI 检查，再完成回滚演练。"
            ),
            citations=[
                {
                    "id": f"action:{a_ci.id}",
                    "source_type": "action",
                    "title": a_ci.title,
                    "excerpt": f"{a_ci.status} · due {a_ci.due_date}",
                    "retro_id": str(r3.id),
                    "action_id": str(a_ci.id),
                    "href_hint": "/actions/board",
                },
                {
                    "id": f"cluster:{cluster.id}",
                    "source_type": "cluster",
                    "title": cluster.canonical_title,
                    "excerpt": "出现 3 次（本周有新出现）",
                    "href_hint": "/trends",
                },
            ],
        )
    )

    if os.getenv("DEMO_INDEX_CONTENT", "").strip().lower() in {"1", "true", "yes"}:
        from app.services import indexing as indexing_service

        for retro in (r1, r2, r3):
            indexing_service.index_retro_content(db, user_id=user.id, retro=retro)

    db.commit()
    db.refresh(user)
    return user


def ensure_demo_account(db: Session) -> User:
    """Keep demo@example.com / demo1234 available without wiping existing sample data.

    Creates the user and story if missing. If the user exists but has no retros,
    rebuilds the story. Always resets the password so the published credentials work.
    """
    existing = db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if existing is None:
        return seed_demo(db)

    existing.password_hash = hash_password(DEMO_PASSWORD)
    has_retro = db.scalar(select(Retro.id).where(Retro.user_id == existing.id).limit(1))
    db.commit()
    if has_retro is None:
        return seed_demo(db)
    return existing


def _at(day: date, hour: int = 8) -> datetime:
    return datetime.combine(day, datetime.min.time(), tzinfo=UTC).replace(hour=hour)


def _retro(
    user: User,
    *,
    retro_type: str,
    title: str,
    review_date: date,
    created_at: datetime,
    raw_content: str,
    summary: dict,
) -> Retro:
    return Retro(
        id=uuid4(),
        user_id=user.id,
        type=retro_type,
        title=title,
        review_date=review_date,
        raw_content=raw_content,
        status="published",
        index_status="pending",
        analysis_summary=summary,
        created_at=created_at,
        updated_at=created_at,
    )


def _problem(
    user: User,
    retro: Retro,
    cluster: ProblemCluster,
    *,
    match_status: str,
) -> ProblemOccurrence:
    return ProblemOccurrence(
        id=uuid4(),
        user_id=user.id,
        retro_id=retro.id,
        cluster_id=cluster.id,
        title=_CHECKLIST,
        normalized_statement=_NORMALIZED,
        category="delivery",
        severity="high",
        source_quote="这次又漏了数据库迁移检查",
        disposition="kept",
        match_status=match_status,
        created_at=retro.created_at,
    )


def _draft(
    user: User,
    retro: Retro,
    problem: ProblemOccurrence,
    *,
    title: str,
    description: str,
    criteria: str,
) -> ActionDraft:
    return ActionDraft(
        id=uuid4(),
        user_id=user.id,
        retro_id=retro.id,
        problem_occurrence_id=problem.id,
        title=title,
        description=description,
        suggested_success_criteria=criteria,
    )


def _action(
    user: User,
    retro: Retro,
    problem: ProblemOccurrence,
    *,
    title: str,
    description: str,
    owner: str,
    due_date: date,
    criteria: str,
    status: str,
    created_at: datetime,
    verified_at: datetime | None = None,
) -> ActionItem:
    return ActionItem(
        id=uuid4(),
        user_id=user.id,
        retro_id=retro.id,
        problem_occurrence_id=problem.id,
        title=title,
        description=description,
        owner=owner,
        due_date=due_date,
        success_criteria=criteria,
        status=status,
        verified_at=verified_at,
        created_at=created_at,
        updated_at=created_at,
    )


def _event(
    user: User,
    action: ActionItem,
    event_type: str,
    *,
    at: datetime,
    from_status: str | None = None,
    to_status: str | None = None,
    note: str | None = None,
    evidence_text: str | None = None,
    evidence_url: str | None = None,
) -> ActionEvent:
    return ActionEvent(
        id=uuid4(),
        user_id=user.id,
        action_id=action.id,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        note=note,
        evidence_text=evidence_text,
        evidence_url=evidence_url,
        created_at=at,
    )


def main() -> None:
    db = SessionLocal()
    try:
        user = seed_demo(db)
        print(f"demo user ready: {DEMO_EMAIL} / {DEMO_PASSWORD} (id={user.id})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
