import pytest

from api.services.prescription_upload import _type_ordonnance
from api.validation import InvoiceRejected


class CodeConnection:
    def execute(self, query):
        assert query == "SELECT code_medicament FROM referentiel_medicaments"
        return [{"code_medicament": "MED-1"}, {"code_medicament": "MED-2"}]


def test_type_ordonnance_is_medicaments_when_all_codes_are_medicaments():
    assert _type_ordonnance(CodeConnection(), ["MED-1", "MED-2"], "CONSULTATION") == "MEDICAMENTS"


@pytest.mark.parametrize(
    ("invoice_type", "expected"),
    [
        ("LABORATOIRE", "EXAMENS"),
        ("IMAGERIE", "EXAMENS"),
        ("KINESITHERAPIE", "KINE"),
        ("OPTIQUE", "OPTIQUE"),
    ],
)
def test_type_ordonnance_maps_invoice_categories(invoice_type, expected):
    assert _type_ordonnance(CodeConnection(), ["ACT-1"], invoice_type) == expected


def test_type_ordonnance_rejects_ambiguous_invoice_category():
    with pytest.raises(InvoiceRejected) as exc:
        _type_ordonnance(CodeConnection(), ["ACT-1"], "CONSULTATION")

    assert exc.value.erreurs[0]["code"] == "TYPE_ORDONNANCE_INDETERMINE"
