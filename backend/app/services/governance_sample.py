SAMPLE_GOVERNANCE_DOC = """# PMO Governance Manual

## 1. Project Health Classification

Projects are classified using a RAG (Red/Amber/Green) status:
- **Green**: On track, no significant issues
- **Amber**: At risk — intervention required within 1 sprint
- **Red**: Critical — escalate to steering committee within 48 hours

## 2. Risk Escalation Procedures

When a risk is rated **High**, the PMO must:
1. Log the risk in the RAID register within 24 hours
2. Notify the project sponsor and PMO director
3. Present mitigation plan at the next steering committee
4. If overdue critical-path items exceed 5 days, escalate to executive leadership

## 3. Sprint Governance

Sprint slippage of more than 2 days requires:
- Scope re-baseline with product owner approval
- Revised delivery forecast communicated to stakeholders
- Resource reallocation assessment by PMO

## 4. Vendor & Dependency Management

All vendor dependencies must have:
- Named owner and escalation contact
- Due date tracked in Jira
- Fallback plan documented before sprint commitment

Delays exceeding 14 days trigger automatic PMO review and steering committee agenda item.

## 5. Resource Bottleneck Policy

If any team member exceeds 8 concurrent open items:
- PMO initiates workload rebalancing review
- Non-critical items deferred to subsequent sprint
- Temporary capacity augmentation considered

## 6. Reporting Cadence

| Report | Frequency | Audience |
|--------|-----------|----------|
| Weekly Status | Every Friday | Project team + PMO |
| Monthly Portfolio | First Monday | PMO leadership |
| Steering Committee | Monthly | Executive sponsors |
"""
