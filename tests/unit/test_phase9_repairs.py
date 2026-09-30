from types import SimpleNamespace
import pytest
from google.genai import types
from app.agent import load_farmer_profile, _hitl_checkpoint_impl, detect_language
from google.adk.sessions import InMemorySessionService

# =============================================================================
# 1. DYNAMIC INPUT-LANGUAGE DETECTION TESTS
# =============================================================================

def test_language_detection_english_input():
    """English input -> Output Language must be English."""
    ctx = SimpleNamespace(state={})
    inp = types.Content(parts=[types.Part.from_text(text="What crop should I grow?")])
    event = load_farmer_profile(ctx, inp)
    profile = ctx.state["farmer_profile"]
    assert profile["language"] == "English"
    assert "IMPORTANT LANGUAGE DIRECTIVE: The target Output Language is English" in event.output
    assert "- Language: English" in event.output

def test_language_detection_hindi_input():
    """Hindi input -> Output Language must be Hindi."""
    ctx = SimpleNamespace(state={})
    inp = types.Content(parts=[types.Part.from_text(text="मुझे गेहूं के बारे में बताओ")])
    event = load_farmer_profile(ctx, inp)
    profile = ctx.state["farmer_profile"]
    assert profile["language"] == "Hindi"
    assert "IMPORTANT LANGUAGE DIRECTIVE: The target Output Language is Hindi" in event.output
    assert "- Language: Hindi" in event.output

def test_language_mid_conversation_switch():
    """English -> Hindi -> English switches dynamically per turn."""
    ctx = SimpleNamespace(state={})
    
    # Turn 1: English
    inp1 = types.Content(parts=[types.Part.from_text(text="What should I grow?")])
    load_farmer_profile(ctx, inp1)
    assert ctx.state["farmer_profile"]["language"] == "English"
    
    # Turn 2: Hindi
    inp2 = types.Content(parts=[types.Part.from_text(text="मुझे गेहूं के बारे में बताओ")])
    load_farmer_profile(ctx, inp2)
    assert ctx.state["farmer_profile"]["language"] == "Hindi"
    
    # Turn 3: English
    inp3 = types.Content(parts=[types.Part.from_text(text="What about irrigation?")])
    load_farmer_profile(ctx, inp3)
    assert ctx.state["farmer_profile"]["language"] == "English"

def test_numeric_coordinates_preserve_current_conversational_language():
    """Purely numeric coordinates do not alter active language."""
    # Previous conversation was in Hindi
    ctx = SimpleNamespace(state={
        "farmer_profile": {
            "language": "Hindi",
            "location": "Maharashtra",
            "latitude": None,
            "longitude": None,
            "crops": [],
            "farm_size": "Unknown",
            "season": None
        }
    })
    
    # User sends coordinates only
    inp = types.Content(parts=[types.Part.from_text(text="16.758842, 74.032992")])
    event = load_farmer_profile(ctx, inp)
    profile = ctx.state["farmer_profile"]
    
    # Coordinates extracted but Hindi preserved
    assert profile["latitude"] == pytest.approx(16.758842, rel=1e-5)
    assert profile["longitude"] == pytest.approx(74.032992, rel=1e-5)
    assert profile["language"] == "Hindi"
    assert "IMPORTANT LANGUAGE DIRECTIVE: The target Output Language is Hindi" in event.output

@pytest.mark.asyncio
async def test_hitl_resume_with_hindi_input_sets_hindi():
    """HITL resume with Hindi response sets Hindi."""
    ctx = SimpleNamespace(
        state={
            "user_query": "What crop should I grow?",
            "farmer_profile": {
                "language": "English",
                "location": "Punjab",
                "latitude": 30.9,
                "longitude": 75.8,
                "crops": [],
                "farm_size": "5 acres",
                "season": None,
            }
        },
        resume_inputs={"more_info": {"result": "खरीफ"}}
    )
    
    events = [e async for e in _hitl_checkpoint_impl(ctx, None)]
    assert len(events) == 1
    event = events[0]
    assert ctx.state["farmer_profile"]["language"] == "Hindi"
    assert "IMPORTANT LANGUAGE DIRECTIVE: The target Output Language is Hindi" in event.output

@pytest.mark.asyncio
async def test_hitl_resume_with_english_input_sets_english():
    """HITL resume with English response sets English."""
    ctx = SimpleNamespace(
        state={
            "user_query": "कौन सी फसल उगाएं?",
            "farmer_profile": {
                "language": "Hindi",
                "location": "Punjab",
                "latitude": 30.9,
                "longitude": 75.8,
                "crops": [],
                "farm_size": "5 acres",
                "season": None,
            }
        },
        resume_inputs={"more_info": {"result": "Kharif"}}
    )
    
    events = [e async for e in _hitl_checkpoint_impl(ctx, None)]
    assert len(events) == 1
    event = events[0]
    assert ctx.state["farmer_profile"]["language"] == "English"
    assert "IMPORTANT LANGUAGE DIRECTIVE: The target Output Language is English" in event.output


# =============================================================================
# 2. HOME RESET & FRESH SESSION TESTS
# =============================================================================

def test_home_reset_clears_coordinates_and_profile_and_creates_fresh_adk_session():
    """Brand/home click resets coordinates, profile, session."""
    session_service = InMemorySessionService()
    
    # 1. Active conversation with Maharashtra farm coordinates
    s1 = session_service.create_session_sync(user_id="user1", app_name="app")
    s1.state["farmer_profile"] = {
        "language": "Hindi",
        "latitude": 16.758842,
        "longitude": 74.032992,
        "location": "Maharashtra",
        "crops": ["sugarcane"],
        "farm_size": "10 acres"
    }
    
    # 2. Frontend state reset on goHome()
    frontend_state = {
        "sessionId": s1.id,
        "lat": 16.758842,
        "lon": 74.032992,
    }
    frontend_state["lat"] = None
    frontend_state["lon"] = None
    
    # 3. Create fresh session
    s2 = session_service.create_session_sync(user_id="user1", app_name="app")
    frontend_state["sessionId"] = s2.id
    
    # Assertions on pristine session
    assert s2.id != s1.id
    assert "farmer_profile" not in s2.state
    assert frontend_state["lat"] is None
    assert frontend_state["lon"] is None

def test_environmental_request_after_home_reset_requires_coordinates_again():
    """After home reset, environmental request on fresh session does not have coordinates."""
    ctx = SimpleNamespace(state={})
    
    inp = types.Content(parts=[types.Part.from_text(text="खेत पर्यावरण का विश्लेषण करें")])
    event = load_farmer_profile(ctx, inp)
    profile = ctx.state["farmer_profile"]
    
    assert profile["latitude"] is None
    assert profile["longitude"] is None
    assert "Coordinates:" not in event.output
    assert profile["language"] == "Hindi"
