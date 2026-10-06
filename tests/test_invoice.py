# -*- coding: utf-8 -*-
"""STATE G7 청구서 게이트: 税込분리 계산 + 미등록 폴백 + 미지プラン 거부."""
from __future__ import annotations

import os
import tempfile

import pytest


def test_invoice_math_and_file():
    from exporter.invoice_pdf import generate_invoice_pdf
    pdf = os.path.join(tempfile.mkdtemp(), "inv.pdf")
    meta = generate_invoice_pdf("u-test-1", "single", output_pdf_path=pdf)
    assert os.path.exists(meta["path"]) and os.path.getsize(meta["path"]) > 1000
    assert meta["total_incl"] == 1500
    assert meta["tax"] == 136  # 1500*10/110 반올림
    assert meta["excl"] == 1500 - 136
    assert meta["invoice_no"].startswith("INV-")


def test_invoice_unknown_plan_rejected():
    from exporter.invoice_pdf import generate_invoice_pdf
    with pytest.raises(ValueError):
        generate_invoice_pdf("u-test-1", "platinum",
                             output_pdf_path=os.path.join(tempfile.mkdtemp(), "x.pdf"))


def test_invoice_unregistered_fallback_present():
    from exporter.invoice_pdf import generate_invoice_pdf
    pdf = os.path.join(tempfile.mkdtemp(), "inv2.pdf")
    meta = generate_invoice_pdf("u-test-2", "basic", output_pdf_path=pdf,
                                invoice_registration_number="")
    assert os.path.exists(meta["path"])
