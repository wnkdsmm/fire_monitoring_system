from __future__ import annotations


def _build_slice_label(
    selected_district: str | None,
    selected_cause: str | None,
    selected_object_category: str | None,
) -> str:
    slice_parts: list[str] = []
    if selected_district and selected_district.strip():
        slice_parts.append(f"район: {selected_district}")
    if selected_cause and selected_cause.strip():
        slice_parts.append(f"причина: {selected_cause}")
    if selected_object_category and selected_object_category.strip():
        slice_parts.append(f"категория: {selected_object_category}")
    return " | ".join(slice_parts) if slice_parts else "Все пожары выбранной истории"
