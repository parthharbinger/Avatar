"""
Tests for the 3 Industry Avatars (E-Commerce, Healthcare, Banking).
Verifies profile retrieval, document indexation, and grounded RAG knowledge search.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.rag_service import list_profiles, retrieve_context_with_sources


@pytest.fixture(autouse=True)
async def run_lifespan():
    async with app.router.lifespan_context(app):
        yield


@pytest.mark.asyncio
async def test_industry_avatar_profiles_exist():
    """Verify that E-Commerce, Healthcare, and Banking avatar profiles are loaded."""
    profiles = list_profiles()
    assert len(profiles) >= 3

    personas = {p.get("persona") for p in profiles}
    assert "ecommerce" in personas
    assert "healthcare" in personas
    assert "banking" in personas


@pytest.mark.asyncio
async def test_ecommerce_rag_retrieval():
    """Verify BM25 knowledge search on the E-Commerce knowledge base."""
    profiles = list_profiles()
    ecom = next(p for p in profiles if p.get("persona") == "ecommerce")
    assert len(ecom["documents"]) > 0

    result = retrieve_context_with_sources(ecom["profile_id"], "What is the 30-day return policy and shipping?")
    assert len(result["context"]) > 0
    assert len(result["sources"]) > 0
    context_lower = result["context"].lower()
    assert "return" in context_lower or "shipping" in context_lower


@pytest.mark.asyncio
async def test_healthcare_rag_retrieval():
    """Verify BM25 knowledge search on the Healthcare knowledge base."""
    profiles = list_profiles()
    health = next(p for p in profiles if p.get("persona") == "healthcare")
    assert len(health["documents"]) > 0

    result = retrieve_context_with_sources(health["profile_id"], "Which insurance plans and telehealth are accepted?")
    assert len(result["context"]) > 0
    assert len(result["sources"]) > 0
    context_lower = result["context"].lower()
    assert "insurance" in context_lower or "telehealth" in context_lower or "clinic" in context_lower


@pytest.mark.asyncio
async def test_banking_rag_retrieval():
    """Verify BM25 knowledge search on the Banking knowledge base."""
    profiles = list_profiles()
    bank = next(p for p in profiles if p.get("persona") == "banking")
    assert len(bank["documents"]) > 0

    result = retrieve_context_with_sources(bank["profile_id"], "What is the APY interest rate on savings accounts?")
    assert len(result["context"]) > 0
    assert len(result["sources"]) > 0
    context_lower = result["context"].lower()
    assert "savings" in context_lower or "apy" in context_lower or "rate" in context_lower


@pytest.mark.asyncio
async def test_get_profiles_api_endpoint():
    """Verify GET /api/v1/profiles returns the 3 industry avatars via REST."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/profiles")
    assert resp.status_code == 200
    profiles = resp.json()
    names = [p["name"] for p in profiles]
    assert any("E-Commerce" in n or "Elena" in n for n in names)
    assert any("Healthcare" in n or "Maya" in n for n in names)
    assert any("Banking" in n or "Alexander" in n for n in names)


@pytest.mark.asyncio
async def test_health_query_to_banking_avatar_instant_rejection():
    """
    Verify that sending a medical/health question to the Banking avatar (Alexander)
    does NOT hang and immediately returns an out-of-domain boundary message redirecting to Dr. Maya.
    """
    profiles = list_profiles()
    bank = next(p for p in profiles if p.get("persona") == "banking")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/chat/respond",
            json={
                "message": "What is the recommended dosage for paracetamol and how to treat fever?",
                "profile_id": bank["profile_id"],
            }
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["model"] == "rag-boundary-guard"
    reply = data["reply"]
    # Verify it clearly explains it's outside banking knowledge and references Healthcare / Dr. Maya
    assert "Banking" in reply or "financial" in reply or "Crestview" in reply
    assert "Maya" in reply or "Healthcare" in reply or "outside" in reply or "documents" in reply


@pytest.mark.asyncio
async def test_banking_query_to_healthcare_avatar_instant_rejection():
    """
    Verify that sending a banking/mortgage question to the Healthcare avatar (Dr. Maya)
    immediately returns an out-of-domain boundary message redirecting to Alexander.
    """
    profiles = list_profiles()
    health = next(p for p in profiles if p.get("persona") == "healthcare")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/chat/respond",
            json={
                "message": "What is the 30-year mortgage interest rate and savings APY?",
                "profile_id": health["profile_id"],
            }
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["model"] == "rag-boundary-guard"
    reply = data["reply"]
    assert "Health" in reply or "clinical" in reply or "documents" in reply
    assert "Alexander" in reply or "Banking" in reply or "financial" in reply


@pytest.mark.asyncio
async def test_persona_greeting_instant_response():
    """
    Verify that conversational greetings like 'Hello' or 'Who are you?' to an avatar
    return an instant persona greeting without external LLM delay.
    """
    profiles = list_profiles()
    bank = next(p for p in profiles if p.get("persona") == "banking")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/chat/respond",
            json={
                "message": "Hello, who are you and what do you do?",
                "profile_id": bank["profile_id"],
            }
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["model"] == "persona-greeting"
    assert "Alexander" in data["reply"]
    assert "Crestview" in data["reply"]


@pytest.mark.asyncio
async def test_in_domain_banking_query_grounded_answer():
    """
    Verify that in-domain queries return relevant document citations and grounded answers.
    """
    profiles = list_profiles()
    bank = next(p for p in profiles if p.get("persona") == "banking")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/chat/respond",
            json={
                "message": "What is the APY interest rate on savings accounts?",
                "profile_id": bank["profile_id"],
            }
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["sources"] is not None
    assert len(data["sources"]) > 0
    assert "4.85" in data["reply"] or "savings" in data["reply"].lower() or "apy" in data["reply"].lower()


@pytest.mark.asyncio
async def test_ecommerce_query_to_banking_avatar_rejection():
    """
    Verify that sending an e-commerce question to Banking redirects to Elena.
    """
    profiles = list_profiles()
    bank = next(p for p in profiles if p.get("persona") == "banking")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/chat/respond",
            json={
                "message": "What is the 30-day return policy and shipping fee for items?",
                "profile_id": bank["profile_id"],
            }
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["model"] == "rag-boundary-guard"
    assert "Elena" in data["reply"] or "E-Commerce" in data["reply"] or "documents" in data["reply"]


@pytest.mark.asyncio
async def test_unrelated_general_query_to_avatar():
    """
    Verify that an arbitrary query not matching documents returns a clear document refusal.
    """
    profiles = list_profiles()
    bank = next(p for p in profiles if p.get("persona") == "banking")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/chat/respond",
            json={
                "message": "What is the capital city of France and how to bake a cake?",
                "profile_id": bank["profile_id"],
            }
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["model"] == "rag-boundary-guard"
    assert "documents" in data["reply"] or "knowledge base" in data["reply"] or "banking" in data["reply"].lower()


@pytest.mark.asyncio
async def test_healthcare_in_domain_grounded_answer():
    """
    Verify that clinical questions to Dr. Maya return accurate grounded knowledge.
    """
    profiles = list_profiles()
    health = next(p for p in profiles if p.get("persona") == "healthcare")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/chat/respond",
            json={
                "message": "What insurance plans are accepted and how to book telehealth?",
                "profile_id": health["profile_id"],
            }
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["sources"] is not None
    assert len(data["sources"]) > 0
    assert "telehealth" in data["reply"].lower() or "insurance" in data["reply"].lower() or "clinic" in data["reply"].lower()


@pytest.mark.asyncio
async def test_open_ended_avatar_greeting():
    """
    Verify that greeting the open-ended avatar (no profile_id) returns Nova's open-ended greeting
    noting that it is not attached to a specific document knowledge base.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/chat/respond",
            json={
                "message": "Hello, who are you and what document knowledge do you have?",
            }
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["model"] == "persona-greeting"
    assert "Nova" in data["reply"]
    assert "open" in data["reply"].lower() or "knowledge base" in data["reply"].lower() or "document" in data["reply"].lower()



