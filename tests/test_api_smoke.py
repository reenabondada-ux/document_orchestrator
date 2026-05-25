from mainframe_doc_orchestrator.api.app import create_app


def test_create_app_returns_fastapi_with_correct_title():
    """create_app() should build the FastAPI instance without opening any I/O.

    The lifespan (pool, schema init, client construction) only runs when the
    app is actually started by uvicorn or an ASGI test client, so this test
    remains fast and database-free.
    """
    app = create_app()
    assert app.title == "Mainframe Document Orchestrator"
