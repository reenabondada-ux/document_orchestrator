from mainframe_doc_orchestrator.planner import MainframeDocumentPlanner
from mainframe_doc_orchestrator.models import DocumentRequest, RetrievalRequest

def test_planner_builds_sections():
    req = DocumentRequest(system_id="SYS1", retrieval_request=RetrievalRequest(query="q", section_name="batch_flow_overview", system_id="SYS1"))
    plan = MainframeDocumentPlanner().plan(req)
    assert len(plan.sections) >= 5
