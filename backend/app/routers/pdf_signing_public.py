"""Publie le certificat public LECIM utilise pour sceller numeriquement les PDF
officiels (diplomes, attestations, cartes) — permet a quiconque de l'importer
comme certificat de confiance dans son lecteur PDF (Adobe Acrobat...) pour voir
la signature validee sans avertissement, ou de verifier manuellement une
signature avec un outil tiers (openssl...)."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ..pdf_signing import PDF_SIGNING_CERT_PATH

router = APIRouter(prefix="/api/pdf-signing", tags=["pdf-signing"])


@router.get("/certificate")
def pdf_signing_certificate():
    if not PDF_SIGNING_CERT_PATH.exists():
        raise HTTPException(status_code=404, detail="Certificat indisponible")
    return Response(
        content=PDF_SIGNING_CERT_PATH.read_bytes(),
        media_type="application/x-pem-file",
        headers={"Content-Disposition": 'attachment; filename="lecim-pdf-signing.pem"'},
    )
