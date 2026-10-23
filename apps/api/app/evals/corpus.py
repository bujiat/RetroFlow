"""Demo retro sentences used by the labeled eval set.

These strings match the raw_content values created in app.seed_demo.
"""

DEMO_CHUNK_TEXTS = (
    "发布当天才发现数据库迁移没有跑。会上有人说："
    "这次又漏了数据库迁移检查，发布清单还是不全。",
    "第二次发布仍漏了检查项。原文："
    "PR 模板里没有 release checklist，评审过了也能合进主干。",
    "第三次出现发布清单遗漏。原文："
    "这次又漏了数据库迁移检查，CI 没有在缺 migration 时拦住合并。",
)

# High fixed vector scores, and no overlap with the demo keywords.
DISTRACTOR_TEXTS = (
    "本周团建改到周五下午。",
    "食堂新增了两款汤。",
    "工位显示器已申请更换。",
    "报销单要在周三前提交。",
    "会议室投影仪灯泡换了。",
    "请假流程改成线上审批。",
)
