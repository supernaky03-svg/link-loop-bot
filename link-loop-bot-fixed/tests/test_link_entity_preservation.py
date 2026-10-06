from app.bot.services.link_service import strip_visible_links_with_entities


def test_hidden_text_link_survives_visible_url_stripping():
    text = 'Visible https://example.com Hidden'
    # Telegram entity offsets are UTF-16 code units. "Hidden" starts at 28.
    entities = [{'type': 'text_link', 'offset': 28, 'length': 6, 'url': 'https://secret.example'}]
    cleaned, adjusted = strip_visible_links_with_entities(text, entities)
    assert cleaned == 'Visible  Hidden'
    assert adjusted == [{'type': 'text_link', 'offset': 9, 'length': 6, 'url': 'https://secret.example'}]


def test_non_url_formatting_offset_is_adjusted():
    text = 'Bold https://example.com text'
    entities = [{'type': 'bold', 'offset': 0, 'length': 29}]
    cleaned, adjusted = strip_visible_links_with_entities(text, entities)
    assert cleaned == 'Bold  text'
    assert adjusted == [{'type': 'bold', 'offset': 0, 'length': 10}]
