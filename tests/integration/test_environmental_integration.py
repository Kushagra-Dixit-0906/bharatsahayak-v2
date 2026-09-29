# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Integration tests for conversational V1 -> MCP -> V2 environmental intelligence flow."""

from datetime import date
from unittest.mock import AsyncMock, patch
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from google.genai.models import AsyncModels

from app.agent import root_agent
from app.assessment.gemini_types import (
    AgriculturalAssessmentExplanationResponse,
    FarmerAgriculturalResponse,
    GeminiAssessmentContext,
    PresentationPreferences,
    RecommendedNextStep,
    VerifiedFarmerContext,
)
from app.assessment.types import AgriculturalAssessment, AssessmentSufficiency
from app.satellite.types import AnalysisRegionMetadata


def _mock_v2_explanation(language: str = "en") -> AgriculturalAssessmentExplanationResponse:
    region = AnalysisRegionMetadata(
        latitude=26.784146,
        longitude=81.544683,
        radius_m=100.0,
        geometry_type="PointBuffer",
        scale_m=10.0,
    )
    assessment = AgriculturalAssessment(
        status="success",
        reference_date=date(2026, 9, 29),
        region=region,
        overall_condition="normal",
        sufficiency=AssessmentSufficiency(
            is_sufficient=True,
            sources_evaluated_count=4,
            sources_available_count=4,
            sources_fully_available_count=4,
            missing_evidence_sources=[],
            partial_evidence_sources=[],
            sufficiency_summary="All sources available",
        ),
        patterns=[],
        conflicting_signals=[],
    )
    if language == "hi":
        farmer_resp = FarmerAgriculturalResponse(
            language="hi",
            headline="सामान्य पर्यावरणीय स्थिति",
            summary="आपके क्षेत्र में उपग्रह डेटा के अनुसार मिट्टी की नमी और वनस्पति स्वास्थ्य संतोषजनक है।",
            observations=["एनडीवीआई सामान्य स्तर (0.65) पर है।"],
            interpretation="धान की फसल के विकास के लिए परिस्थितियां अनुकूल हैं।",
            recommended_next_steps=[
                RecommendedNextStep(
                    action_type="ongoing_monitoring",
                    description="खेत का नियमित निरीक्षण जारी रखें।",
                    urgency="routine",
                )
            ],
            limitations=["डेटा 100 मीटर के दायरे पर आधारित है।"],
            is_fallback=False,
        )
    else:
        farmer_resp = FarmerAgriculturalResponse(
            language="en",
            headline="Normal Environmental Conditions",
            summary="Satellite observation indicates normal vegetation vigor and satisfactory moisture across your parcel.",
            observations=["Sentinel-2 NDVI is at a healthy baseline of 0.65."],
            interpretation="Conditions are favorable for current crop growth.",
            recommended_next_steps=[
                RecommendedNextStep(
                    action_type="ongoing_monitoring",
                    description="Maintain regular field scouting and standard irrigation schedule.",
                    urgency="routine",
                )
            ],
            limitations=["Observations represent an approximate 100-meter circular buffer."],
            is_fallback=False,
        )
    context = GeminiAssessmentContext(
        overall_condition="normal",
        assessment_status="success",
        reference_date=date(2026, 9, 29),
        region=region,
        identified_patterns=[],
        conflicting_signals=[],
        limitations=farmer_resp.limitations,
        is_sufficient=True,
        missing_evidence_sources=[],
        farmer_context=VerifiedFarmerContext(preferred_language=language),
        presentation=PresentationPreferences(target_language=language),
    )
    return AgriculturalAssessmentExplanationResponse(
        assessment=assessment,
        explanation=farmer_resp,
        context_used=context,
    )


async def mock_orchestrator_stream(*args, **kwargs):
    contents = kwargs.get("contents")
    prompt_text = ""
    if contents:
        if isinstance(contents, list):
            for c in contents:
                if hasattr(c, "parts"):
                    for p in c.parts:
                        if hasattr(p, "text") and p.text:
                            prompt_text += p.text
        elif hasattr(contents, "parts"):
            for p in contents.parts:
                if hasattr(p, "text") and p.text:
                    prompt_text += p.text
        elif isinstance(contents, str):
            prompt_text = contents

    prompt_lower = prompt_text.lower()

    if "what is the environmental situation" in prompt_lower or "environmental condition" in prompt_lower:
        if "location: unknown" in prompt_lower and "coordinates:" not in prompt_lower:
            resp = '{"response": "", "needs_more_info": true, "info_request_message": "To check environmental conditions, please tell me your farm location or district."}'
        else:
            # Calls MCP tool and passes output directly
            resp = (
                '{"response": "🌾 Environmental Assessment (Normal Environmental Conditions)\\n\\n'
                'Satellite observation indicates normal vegetation vigor and satisfactory moisture across your parcel.\\n\\n'
                'Key Observations:\\n- Sentinel-2 NDVI is at a healthy baseline of 0.65.\\n\\n'
                'Interpretation:\\nConditions are favorable for current crop growth.\\n\\n'
                'Recommended Next Steps:\\n- [ongoing_monitoring] Maintain regular field scouting and standard irrigation schedule.\\n\\n'
                'Limitations & Data Freshness:\\n- Observations represent an approximate 100-meter circular buffer.", '
                '"needs_more_info": false, "info_request_message": ""}'
            )
    elif "पर्यावरणीय स्थिति" in prompt_lower:
        if "location: unknown" in prompt_lower and "coordinates:" not in prompt_lower:
            resp = '{"response": "", "needs_more_info": true, "info_request_message": "पर्यावरणीय स्थिति देखने के लिए कृपया अपने खेत का स्थान बताएं।"}'
        else:
            resp = (
                '{"response": "🌾 Environmental Assessment (सामान्य पर्यावरणीय स्थिति)\\n\\n'
                'आपके क्षेत्र में उपग्रह डेटा के अनुसार मिट्टी की नमी और वनस्पति स्वास्थ्य संतोषजनक है।\\n\\n'
                'प्रमुख अवलोकन:\\n- एनडीवीआई सामान्य स्तर (0.65) पर है।\\n\\n'
                'व्याख्या:\\nधान की फसल के विकास के लिए परिस्थितियां अनुकूल हैं।\\n\\n'
                'अनुशंसित अगले कदम:\\n- [ongoing_monitoring] खेत का नियमित निरीक्षण जारी रखें।\\n\\n'
                'सीमाएं व डेटा ताजगी:\\n- डेटा 100 मीटर के दायरे पर आधारित है।", '
                '"needs_more_info": false, "info_request_message": ""}'
            )
    else:
        resp = '{"response": "General farming response", "needs_more_info": false, "info_request_message": ""}'

    chunk = types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(
                    parts=[types.Part.from_text(text=resp)]
                )
            )
        ]
    )
    yield chunk


def test_environmental_query_routing_with_known_location() -> None:
    """Verifies that an environmental query with location routes to environmental assessment without HITL."""
    session_service = InMemorySessionService()
    session = session_service.create_session_sync(user_id="test_farmer_env", app_name="test")
    runner = Runner(agent=root_agent, session_service=session_service, app_name="test")

    message = types.Content(
        role="user",
        parts=[types.Part.from_text(text="What is the environmental situation around my farm in Barabanki?")]
    )

    with patch.object(AsyncModels, "generate_content_stream", side_effect=mock_orchestrator_stream):
        events = list(
            runner.run(
                new_message=message,
                user_id="test_farmer_env",
                session_id=session.id,
                run_config=RunConfig(streaming_mode=StreamingMode.SSE),
            )
        )

    final_response = ""
    for event in events:
        if event.content and event.content.parts:
            final_response += "".join(p.text for p in event.content.parts if p.text)

    assert "🌾 Environmental Assessment (Normal Environmental Conditions)" in final_response
    assert "Sentinel-2 NDVI is at a healthy baseline of 0.65." in final_response
    assert "Recommended Next Steps:" in final_response


def test_environmental_query_missing_location_triggers_hitl_and_resumes() -> None:
    """Verifies that missing location triggers HITL and providing location resumes environmental flow."""
    session_service = InMemorySessionService()
    session = session_service.create_session_sync(user_id="test_farmer_hitl", app_name="test")
    runner = Runner(agent=root_agent, session_service=session_service, app_name="test")

    # Turn 1: Query without location
    message1 = types.Content(
        role="user",
        parts=[types.Part.from_text(text="What is the environmental situation around my farm?")]
    )

    with patch.object(AsyncModels, "generate_content_stream", side_effect=mock_orchestrator_stream):
        events1 = list(
            runner.run(
                new_message=message1,
                user_id="test_farmer_hitl",
                session_id=session.id,
                run_config=RunConfig(streaming_mode=StreamingMode.SSE),
            )
        )

    has_request_input = False
    for event in events1:
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.function_call and part.function_call.name == "adk_request_input":
                    has_request_input = True
                    assert "tell me your farm location" in part.function_call.args.get("message", "")

    assert has_request_input

    # Turn 2: Resume with location "Barabanki"
    part = types.Part(
        function_response=types.FunctionResponse(
            name="adk_request_input",
            id="more_info",
            response={"result": "Barabanki"}
        )
    )
    message2 = types.Content(role="user", parts=[part])

    with patch.object(AsyncModels, "generate_content_stream", side_effect=mock_orchestrator_stream):
        events2 = list(
            runner.run(
                new_message=message2,
                user_id="test_farmer_hitl",
                session_id=session.id,
                run_config=RunConfig(streaming_mode=StreamingMode.SSE),
            )
        )

    final_response2 = ""
    for event in events2:
        if event.content and event.content.parts:
            final_response2 += "".join(p.text for p in event.content.parts if p.text)

    assert "🌾 Environmental Assessment (Normal Environmental Conditions)" in final_response2
    assert "Recommended Next Steps:" in final_response2


def test_environmental_query_hindi_routing() -> None:
    """Verifies that Hindi environmental query with location returns Hindi environmental response."""
    session_service = InMemorySessionService()
    session = session_service.create_session_sync(user_id="test_farmer_hi", app_name="test")
    runner = Runner(agent=root_agent, session_service=session_service, app_name="test")

    message = types.Content(
        role="user",
        parts=[types.Part.from_text(text="बाराबंकी में मेरे खेत की पर्यावरणीय स्थिति कैसी है?")]
    )

    with patch.object(AsyncModels, "generate_content_stream", side_effect=mock_orchestrator_stream):
        events = list(
            runner.run(
                new_message=message,
                user_id="test_farmer_hi",
                session_id=session.id,
                run_config=RunConfig(streaming_mode=StreamingMode.SSE),
            )
        )

    final_response = ""
    for event in events:
        if event.content and event.content.parts:
            final_response += "".join(p.text for p in event.content.parts if p.text)

    assert "🌾 Environmental Assessment (सामान्य पर्यावरणीय स्थिति)" in final_response
    assert "प्रमुख अवलोकन:" in final_response
    assert "अनुशंसित अगले कदम:" in final_response
