"""Non-authoritative, escaped HTML compatibility output for existing render paths."""

from html import escape

from modules.presentations.domain.document import PresentationDocument


def canonical_to_safe_html(document: PresentationDocument) -> str:
    parts = ['<div class="canonical-presentation" data-schema="1.0.0">']
    for slide in sorted(document.slides, key=lambda value: value.order):
        parts.append(f'<section data-slide-id="{slide.id}">')
        for element in slide.elements:
            if element.type == "text":
                text = "\n".join(run.text for paragraph in element.paragraphs for run in paragraph.runs)
                parts.append(f'<p data-element-id="{element.id}">{escape(text)}</p>')
            elif element.type == "image":
                label = escape(element.alt_text or "")
                parts.append(f'<div role="img" aria-label="{label}" data-asset-id="{element.asset_id}"></div>')
            else:
                parts.append(f'<div data-element-id="{element.id}" data-element-type="{element.type}"></div>')
        parts.append("</section>")
    parts.append("</div>")
    return "".join(parts)
