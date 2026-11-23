from dataclasses import replace

import pytest

from app.engine import Editor
from app.errors import EditorError
from app.formats.adapter import Document, SerializedFile
from app.formats.demo import DemoAdapter


def test_export_rejects_serialization_that_changes_other_fields(original):
    class FaultyAdapter(DemoAdapter):
        def serialize(self, document: Document, original: bytes) -> SerializedFile:
            output = super().serialize(document, original)
            return replace(output, data=output.data.replace(b"fixture-backend", b"fixture-altered"))

    with pytest.raises(EditorError) as caught:
        Editor([FaultyAdapter()]).prepare_export(original, {"sample_count": 5}, 1024)
    assert caught.value.error.code == "export_verification_failed"


def test_no_adapter_reports_unsupported_format(original):
    with pytest.raises(EditorError) as caught:
        Editor([]).inspect(original)
    assert caught.value.error.code == "unsupported_format"
