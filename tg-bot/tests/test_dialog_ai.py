from unittest.mock import AsyncMock, patch, MagicMock
from ai.prompts.dialog import build_dialog_prompt

CATALOG = [{"name": "Горбуша", "price_retail": 250.0, "price_wholesale": 185.0,
            "origin": "Камчатка", "in_stock": 1, "unit": "кг"}]
SETTINGS = {"delivery_zones": "Москва, СПб", "delivery_min_order": "5 кг"}


def test_build_dialog_prompt_returns_two_messages():
    msgs = build_dialog_prompt("есть икра?", CATALOG, SETTINGS)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"


def test_build_dialog_prompt_has_no_price_vip():
    catalog_with_vip = [{**CATALOG[0], "price_vip": 999.0}]
    msgs = build_dialog_prompt("есть икра?", catalog_with_vip, SETTINGS)
    full_text = str(msgs)
    assert "price_vip" not in full_text
    assert "999" not in full_text


def test_build_dialog_prompt_includes_manager_contact():
    import config
    msgs = build_dialog_prompt("нужна скидка", CATALOG, SETTINGS)
    system = msgs[0]["content"]
    assert config.MANAGER_CONTACT in system


@patch("ai.dialog._client")
async def test_generate_dialog_response_returns_string(mock_client):
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = "Да, горбуша есть, 250₽/кг"
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
    from ai.dialog import generate_dialog_response
    result = await generate_dialog_response("есть горбуша?", CATALOG, SETTINGS)
    assert isinstance(result, str)
    assert len(result) > 0
