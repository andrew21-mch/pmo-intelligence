from datetime import UTC, datetime

from app.agents.raid_agent import RaidAgent
from app.agents.risk_agent import RiskAgent
from app.agents.schemas import RiskLevel
from app.agents.status_agent import StatusAgent
from app.services.project_context import ProjectContext
from app.services.rag import RAGService
from app.services.raid_service import RaidService
from app.services.text_utils import markdown_to_plain_text


class ReportingAgent:
    TEMPLATES = ("weekly", "monthly", "steering_committee")

    async def generate(
        self,
        ctx: ProjectContext,
        template: str,
        db,
        *,
        rag_hits: list[dict] | None = None,
    ) -> dict:
        template = template if template in self.TEMPLATES else "weekly"

        status = await StatusAgent().analyze(ctx)
        risk = await RiskAgent().analyze(ctx)
        raid_report = await RaidAgent().analyze(ctx)
        await RaidService(db).save_report(raid_report)

        if rag_hits is None:
            rag = RAGService()
            query = f"PMO governance risk escalation procedures for {ctx.project.name}"
            rag_hits = await rag.search(query, limit=3, project_key=ctx.project.key)

        citations = [
            f"[{h['title']}] {markdown_to_plain_text(h['text'], max_len=200)}"
            for h in (rag_hits or [])
        ]

        now = datetime.now(UTC).strftime("%Y-%m-%d")
        title_map = {
            "weekly": f"Weekly Status Report — {ctx.project.name}",
            "monthly": f"Monthly Portfolio Report — {ctx.project.name}",
            "steering_committee": f"Steering Committee Update — {ctx.project.name}",
        }

        markdown = self._build_markdown(
            template=template,
            title=title_map[template],
            date=now,
            project_key=ctx.project.key,
            status=status,
            risk=risk,
            raid_entries=raid_report.entries,
            citations=citations,
        )

        return {
            "template": template,
            "project_key": ctx.project.key,
            "project_name": ctx.project.name,
            "title": title_map[template],
            "generated_at": now,
            "markdown": markdown,
            "html": self._markdown_to_html(markdown, title_map[template]),
            "citations": [
                {
                    "title": h["title"],
                    "excerpt": markdown_to_plain_text(h["text"], max_len=300),
                    "doc_id": h.get("doc_id"),
                }
                for h in (rag_hits or [])
            ],
            "health": status.health.value,
            "risk_score": risk.risk_score.value,
        }

    def _build_markdown(self, *, template, title, date, project_key, status, risk, raid_entries, citations) -> str:
        lines = [
            f"# {title}",
            f"**Project:** {project_key} | **Date:** {date} | **Health:** {status.health.value} | **Risk:** {risk.risk_score.value}",
            "",
            "## Executive Summary",
            status.executive_summary,
            "",
        ]

        if template in ("weekly", "monthly", "steering_committee"):
            lines += [
                "## Project Health",
                f"- Completed stories: **{status.completed_stories}**",
                f"- At-risk stories: **{status.at_risk_stories}**",
                f"- Sprint progress:",
            ]
            for s in status.sprint_progress:
                lines.append(f"  - {s.sprint_name}: {s.completion_pct}% ({s.completed_stories}/{s.total_stories})")
            lines.append("")

        if template == "monthly":
            lines += [
                "## Monthly Highlights",
                f"- Overall risk posture: **{risk.risk_score.value}**",
                f"- RAID entries tracked: **{len(raid_entries)}**",
                f"- Open risk signals: **{len(risk.signals)}**",
                "",
            ]

        lines += [
            "## Risk Assessment",
            risk.reasoning,
            "",
            "### Top Risks",
        ]
        for signal in risk.signals[:5]:
            lines.append(f"- **[{signal.severity.value}]** {signal.description}")
        lines.append("")

        lines += ["## RAID Summary", ""]
        by_type: dict[str, list] = {}
        for entry in raid_entries:
            by_type.setdefault(entry.entry_type.value, []).append(entry)
        for rtype, entries in by_type.items():
            lines.append(f"### {rtype}s ({len(entries)})")
            for e in entries[:3]:
                lines.append(f"- **{e.title}** — {e.impact}")
            lines.append("")

        if template == "steering_committee":
            lines += [
                "## Decisions Required",
            ]
            if risk.risk_score in (RiskLevel.HIGH, RiskLevel.MEDIUM):
                lines.append("- Approve escalation path for overdue critical-path items")
            if status.blocked_issues:
                lines.append(f"- Unblock {len(status.blocked_issues)} blocked items — assign executive sponsor")
            lines.append("- Confirm resource allocation for next sprint")
            lines.append("")

        lines += ["## Recommendations", ""]
        for rec in status.recommendations:
            lines.append(f"- {rec}")
        for action in risk.recommended_actions[:3]:
            if action not in status.recommendations:
                lines.append(f"- {action}")
        lines.append("")

        if citations:
            lines += ["## Governance Context (RAG)", ""]
            for cite in citations:
                lines.append(f"> {cite}")
            lines.append("")

        lines.append("---")
        lines.append("*Generated by PMO Intelligence Platform*")
        return "\n".join(lines)

    @staticmethod
    def _inline_html(text: str) -> str:
        import html
        import re

        escaped = html.escape(text)
        return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)

    @staticmethod
    def _markdown_to_html(markdown: str, title: str) -> str:
        import html

        parts: list[str] = []
        in_list = False

        for line in markdown.splitlines():
            stripped = line.strip()

            if not stripped:
                if in_list:
                    parts.append("</ul>")
                    in_list = False
                continue

            if stripped == "---":
                if in_list:
                    parts.append("</ul>")
                    in_list = False
                parts.append("<hr>")
                continue

            if stripped.startswith("### "):
                if in_list:
                    parts.append("</ul>")
                    in_list = False
                parts.append(f"<h3>{ReportingAgent._inline_html(stripped[4:])}</h3>")
            elif stripped.startswith("## "):
                if in_list:
                    parts.append("</ul>")
                    in_list = False
                parts.append(f"<h2>{ReportingAgent._inline_html(stripped[3:])}</h2>")
            elif stripped.startswith("# "):
                if in_list:
                    parts.append("</ul>")
                    in_list = False
                parts.append(f"<h1>{ReportingAgent._inline_html(stripped[2:])}</h1>")
            elif stripped.startswith("> "):
                if in_list:
                    parts.append("</ul>")
                    in_list = False
                quote_text = markdown_to_plain_text(stripped[2:])
                parts.append(f"<blockquote>{ReportingAgent._inline_html(quote_text)}</blockquote>")
            elif stripped.startswith("- "):
                if not in_list:
                    parts.append("<ul>")
                    in_list = True
                parts.append(f"<li>{ReportingAgent._inline_html(stripped[2:])}</li>")
            elif stripped.startswith("*") and stripped.endswith("*"):
                if in_list:
                    parts.append("</ul>")
                    in_list = False
                parts.append(f'<p class="footer"><em>{ReportingAgent._inline_html(stripped.strip("*"))}</em></p>')
            else:
                if in_list:
                    parts.append("</ul>")
                    in_list = False
                parts.append(f"<p>{ReportingAgent._inline_html(stripped)}</p>")

        if in_list:
            parts.append("</ul>")

        body = "\n".join(parts)

        return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; max-width: 820px; margin: 2rem auto; padding: 0 1.5rem 3rem; color: #0f172a; line-height: 1.65; background: #fff; }}
  h1 {{ font-size: 1.75rem; border-bottom: 2px solid #1d4ed8; padding-bottom: 0.5rem; margin-bottom: 0.5rem; }}
  h2 {{ font-size: 1.2rem; color: #1e40af; margin-top: 1.75rem; margin-bottom: 0.5rem; }}
  h3 {{ font-size: 1rem; color: #334155; margin-top: 1.25rem; margin-bottom: 0.35rem; }}
  p {{ margin: 0.5rem 0; }}
  ul {{ margin: 0.5rem 0 1rem; padding-left: 1.5rem; }}
  li {{ margin-bottom: 0.4rem; }}
  blockquote {{ background: #f0f9ff; border-left: 4px solid #3b82f6; padding: 0.75rem 1rem; margin: 1rem 0; font-size: 0.92rem; color: #334155; border-radius: 0 6px 6px 0; }}
  hr {{ border: none; border-top: 1px solid #e2e8f0; margin: 1.5rem 0; }}
  .footer {{ color: #64748b; font-size: 0.85rem; margin-top: 2rem; }}
  strong {{ color: #0f172a; }}
</style></head><body>{body}</body></html>"""
